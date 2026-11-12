# -*- coding: utf-8 -*-
"""主升浪档位判断：把一只票当前所在阶段归到 A/B/C 档，回答"离主升浪还有多远"。

不是预测"哪天爆发"，而是给"现在处于技术上的哪个位置"，配合等"启动确认周"操作。

规则口径（与全局 config.MAIN_WAVE_RULE 一致）：
  · MA55 / MA233 = 收盘价的55/233日均线
  · MACD(12,26,9)，强/弱按 DIF/DEA 相对0轴
  · $距离55$ = (现价 - MA55) / MA55

--------------------------------------------------------------
档位定性表（判断离主升浪多远）
--------------------------------------------------------------
C档 · 蓄势/未启 · 离主升浪最远   条件（在周与日两个级别上都满足才算稳）
  - 周/日的 MACD 仍多在0轴下方（或刚回踩），价格在55/233下方或者刚站，方向未成。
  - 例子：同花顺(0轴下、55下) 早期低位的券商亦可。

B档 · 启动口/前夜 · 离主升浪很近（候选 + 等启动阳确认）
  - 已经历过明显下跌，价格回到 55 线上方、贴近55线（|距离55| 小）；
  - 周/日 MACD 刚翻上0轴（DIF 贴0轴上沿、或刚金叉），仍"在0轴上沿犹豫"，柱徘徊；
  - 未大幅脱离55线（尚未 +45%那样暴涨），前方一般还有不远的压力前高/旧平台。
  → 此时属"前夜埋伏候选区"：可轻仓试，等下面的启动确认，不满仓赌某日发动。

（启动确认：单周/当根出现 放量大阳、价脱离55 >10%、且 DIF 重新上穿 DEA/0轴 加速）
--------------------------------------------------------------
（启动确认周后）到 A档：
A档 · 已入主升中后段（强但追高风险）
  - 周MACD 长期0轴上方、价格远脱离55线（距离55 大），涨幅已显著、涨了很久。
  - 例子：招金黄金(乖离+34%上方)。此时多为"别追、等深度回踩或离场分批"。
--------------------------------------------------------------
"""
import pandas as pd


def macd_df(df, fast=12, slow=26, signal=9):
    """给含 close 的 df 追加 dif/dea/hist/ma55/ma233，返回副本。"""
    out = df.copy()
    c = out["close"]
    ema_f = c.ewm(span=fast, adjust=False).mean()
    ema_s = c.ewm(span=slow, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=signal, adjust=False).mean()
    out["dif"], out["dea"], out["hist"] = dif, dea, (dif - dea) * 2
    out["ma55"], out["ma233"] = c.rolling(55).mean(), c.rolling(233).mean()
    return out


def zone(dif, dea):
    """按快慢线相对0轴给"强弱区"。"""
    if dif > 0 and dea > 0:
        return "强区0轴上"
    if dif > 0 >= dea:
        return "极强孕育(DIF上0轴,DEA待上)"
    if dif < 0 < dea:
        return "高位转弱"
    if dif < 0 and dea < 0:
        return "弱区0轴下"
    return "0轴临界"


def classify_single(week_zone, day_zone, gap55):
    """把一票（周/日强弱区 + 距55线 已算好）归类到档位。"""
    w_s = week_zone.startswith("强区") or week_zone.startswith("极强")
    d_s = day_zone.startswith("强区") or day_zone.startswith("极强")

    # A档：周/日0轴上强(B级强) 且 价已大幅脱离55线(>22%) → 主升中后段
    if w_s and gap55 > 0.22:
        return {"档": "A", "caveat": f"周转好0轴上且距55 {gap55*100:+.0f}%>22%，主升中/后段，追高风险大",
                "can_enter": False,
                "wait_what": "别追高：等深回踩55或箱体低吸，或分批了结，防主升末端急跌。"}
    # B挡：周/日都是0轴上强(大级别与小级别方向一致向好拉、价离55不远→顺势/启动初段)
    if w_s and d_s:
        return {"档": "B", "caveat": "周/日0轴上双强、价未大幅脱离55，主升初段/启动口",
                "can_enter": True,
                "wait_what": ("可顺势：回踩55企稳低吸，或放量脱离头上前高(第一道闸)再加仓；"
                              "价贴55未拉远时仍属启动初期，仓位分批别一把梭。")}
    # 临门一脚：周已0轴上、但日线回踩55/e未跟上来(弱/未翻红)
    if w_s and not d_s:
        return {"档": "C→B", "caveat": "周(大级别)已0轴上、但日线还未跟上(回踩/未翻红)，临门一脚待确认",
                "can_enter": False,
                "wait_what": "盯日线站回55/0轴上且放量=发动；若跌破55则先回避，别抢猜。"}
    # C档：周还在0轴下弱区，离主升还早
    return {"档": "C", "caveat": "周在0轴下(弱区)或未站稳，主升浪还早",
            "can_enter": False,
            "wait_what": "先不做：价站回55/233上方且MACD上0轴金叉、绿柱转红后再谈。"}


def describe(code, week_zone, day_zone, gap55):
    """用规则落地成可读结论。"""
    r = classify_single(week_zone, day_zone, gap55)
    print(f"[{code}] 档位={r['档']}  周={week_zone} | 日={day_zone} | 距55线={gap55*100:+.1f}%")
    print(f"  性质: {r['caveat']}")
    print(f"  该做什么: {r['wait_what']}")
    return r
