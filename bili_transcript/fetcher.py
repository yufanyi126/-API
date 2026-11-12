# -*- coding: utf-8 -*-
"""B 站视频 AI 字幕抓取模块。

基于 B 站官方接口拉取视频的 AI 自动字幕（语言代码 ai-zh）。

流程：
  1. 用 SESSDATA 登录态（Cookie）访问 B 站接口；
  2. 通过 bvid 获取视频信息 (cid、标题)；
  3. 通过播放信息接口拿到 AI 字幕下载地址；
  4. 下载字幕 JSON 并解析成结构化字幕。

SESSDATA 从配置读取（默认 cache/bilibili_config.json），不硬编码在代码中。
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

import requests

# 默认配置路径：cache 目录（已被 .gitignore 排除，避免泄露登录态）
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "cache", "bilibili_config.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


# ----------------------------------------------------------------------
# 配置读取
# ----------------------------------------------------------------------
def load_sessdata(config_path: Optional[str] = None) -> str:
    """从配置读取 SESSDATA。"""
    path = config_path or DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"找不到 B 站配置文件: {path}\n"
            "请创建该文件并写入 {\"SESSDATA\": \"你的SESSDATA值\"}，"
            "或通过 bilibili_helper.save_sessdata() 保存。")
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    sess = cfg.get("SESSDATA", "")
    if not sess:
        raise ValueError("配置中缺少 SESSDATA（登录态已过期？）")
    return sess


def save_sessdata(sessdata: str,
                  config_path: Optional[str] = None) -> str:
    """保存 SESSDATA 到配置（用于首次配置 / 登录态过期后更新）。"""
    path = config_path or DEFAULT_CONFIG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"SESSDATA": sessdata}, f, ensure_ascii=False, indent=2)
    return path


# ----------------------------------------------------------------------
# 会话管理
# ----------------------------------------------------------------------
def build_session(sessdata: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com/",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": f"SESSDATA={sessdata}",
    })
    return s


# ----------------------------------------------------------------------
# 核心接口
# ----------------------------------------------------------------------
def _get_player_info(session: requests.Session, bvid: str, cid: int) -> dict:
    """获取播放信息，解析出 AI 字幕下载地址。"""
    url = ("https://api.bilibili.com/x/player/wbi/v2"
           f"?bvid={bvid}&cid={cid}")
    r = session.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取播放信息失败: code={data.get('code')} "
                           f" msg={data.get('message')}")
    return data


def _download_subtitles(session: requests.Session, subtitle_url: str) -> List[dict]:
    """下载并解析字幕 JSON，返回 [{from, to, content}] 列表。"""
    url = subtitle_url
    if url.startswith("//"):
        url = "https:" + url
    r = session.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("body", [])


def get_subtitles(
    bvid: str,
    sessdata: Optional[str] = None,
    session: Optional[requests.Session] = None,
    prefer_lang: str = "ai-zh",
) -> Dict:
    """获取指定 BVID 视频的 AI 字幕。

    参数
    ----
    bvid : str
        B 站视频的 BVID（如 "BV1Vptt6uEDW"）。
    sessdata : str, optional
        B 站登录 Cookie 里的 SESSDATA；默认从配置读取。
    session : requests.Session, optional
        复用会话，避免重复构建。
    prefer_lang : str
        优先选择的字幕语言，默认 "ai-zh"（AI 自动字幕）。

    返回
    ----
    dict : {
        'bvid': str,
        'title': str,
        'lang': str,
        'entries': [{'from': float, 'to': float, 'content': str}, ...],
        'text': str   # 带时间戳的纯文本
    }
    """
    if sessdata is None:
        sessdata = load_sessdata()
    own = session is None
    s = session or build_session(sessdata)

    try:
        # 1. 拿视频信息（cid, 标题）
        info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        r = s.get(info_url, timeout=15)
        r.raise_for_status()
        info = r.json()
        if info.get("code") != 0:
            raise RuntimeError(f"获取视频信息失败: code={info.get('code')} "
                               f" msg={info.get('message')} (BVID 不存在或需要登录？)")
        vdata = info["data"]
        cid = vdata["cid"]
        title = vdata.get("title", bvid)

        # 2. 拿字幕列表
        player = _get_player_info(s, bvid, cid)
        subs = player.get("data", {}).get("subtitle", {}).get("subtitles", [])
        if not subs:
            return {"bvid": bvid, "title": title, "lang": None,
                    "entries": [], "text": "",
                    "reason": "该视频没有可用字幕（可能没有开启 AI 字幕）"}

        # 选优先语言
        chosen = None
        for x in subs:
            if x.get("lan") == prefer_lang:
                chosen = x
                break
        if chosen is None:
            chosen = subs[0]
        lang = chosen.get("lan")

        # 3. 下载字幕
        entries = _download_subtitles(s, chosen.get("subtitle_url", ""))

        # 生成文本
        lines = []
        for seg in entries:
            t = seg.get("from", 0)
            mm = int(t // 60); ss = int(t % 60)
            hh = int(t // 3600)
            if hh > 0:
                stamp = f"{hh}:{mm:02d}:{ss:02d}"
            else:
                stamp = f"{mm:02d}:{ss:02d}"
            lines.append(f"[{stamp}] {seg.get('content', '')}")
        text = "\n".join(lines)

        return {"bvid": bvid, "title": title, "lang": lang,
                "entries": entries, "text": text}
    finally:
        if own:
            s.close()


def fetch_and_save(bvid: str,
                   output_dir: str = "results/bilibili",
                   config_path: Optional[str] = None) -> Dict:
    """抓取字幕并保存到 results/bilibili/<bvid>.txt。"""
    result = get_subtitles(bvid)
    os.makedirs(output_dir, exist_ok=True)
    safe = bvid.replace("/", "").replace("\\", "")
    path = os.path.join(output_dir, f"{safe}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {result['title']}\n")
        f.write(f"# BVID: {bvid}   字幕: {result['lang']}\n\n")
        f.write(result["text"])
    result["file"] = path
    return result
