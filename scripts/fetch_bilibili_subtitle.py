# -*- coding: utf-8 -*-
"""命令行工具：抓取 B 站视频 AI 字幕。

用法：
    python scripts/fetch_bilibili_subtitle.py BV1Vptt6uEDW
    python scripts/fetch_bilibili_subtitle.py https://www.bilibili.com/video/BV1Vptt6uEDW/
    python scripts/fetch_bilibili_subtitle.py --save BV1xxx

可选参数：
    -s / --save        把字幕保存到 results/bilibili/<bvid>.txt
    -i / --init SESS   保存 SESSDATA 到配置（首次配置或更新登录态）

示例：
    # 首次配置登录态
    python scripts/fetch_bilibili_subtitle.py --init 你的SESSDATA
    # 抓取并保存字幕
    python scripts/fetch_bilibili_subtitle.py --save BV1Vptt6uEDW
"""
import argparse
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bili_transcript import get_subtitles, fetch_and_save, save_sessdata

BVID_RE = re.compile(r"[Bb][Vv][a-zA-Z0-9]{10}")


def extract_bvid(text: str) -> str:
    m = BVID_RE.search(text)
    if m:
        return m.group(0)
    return text


def main():
    parser = argparse.ArgumentParser(description="抓取 B 站视频 AI 字幕")
    parser.add_argument("bvid", nargs="?", help="BVID 或视频链接")
    parser.add_argument("-s", "--save", action="store_true",
                        help="把字幕保存到 results/bilibili/")
    parser.add_argument("-i", "--init", metavar="SESSDATA",
                        help="保存 SESSDATA 登录态（首次配置/更新）")
    args = parser.parse_args()

    if args.init:
        path = save_sessdata(args.init)
        print(f"已保存 SESSDATA 到: {path}")

    if not args.bvid:
        parser.print_help()
        return

    bvid = extract_bvid(args.bvid)
    print(f"抓取字幕: {bvid}")

    try:
        if args.save:
            result = fetch_and_save(bvid)
            print(f"已保存到: {result['file']}")
        else:
            result = get_subtitles(bvid)

        if result.get("reason"):
            print("提示:", result["reason"])
            return

        title = result.get("title", bvid)
        lang = result.get("lang", "未知")
        n = len(result.get("entries", []))
        print(f"标题: {title}  字幕语言: {lang}  共 {n} 条")
        print("=" * 50)
        print(result.get("text", ""))
    except Exception as e:
        print(f"出错: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
