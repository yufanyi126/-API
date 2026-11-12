# -*- coding: utf-8 -*-
"""左侧·安全垫/抗跌 判档策略（与右侧 main_wave 完全分开）

回答的问题（对"已持有/考虑买入、核心是跌不下去"的持仓）：
  · 这一笔下面还有没有"垫"（离历史底部/成本密集区近不近）？
  · 现在是在"下跌通道里、还没止跌"，还是已经"站回55线上、脱离跳水楼梯"？
  · 若大盘踩"第二只脚"，这笔是相对抗跌(浅跌能接回)，还是最容易被拖下去(仍在下楼梯)？

核心差别（务必区分，不要混用）：
  - main_wave(A/B/C) = 右侧尺：问"会不会马上进主升浪 / 买了会不会立刻涨"。用它做买入择时。
  - safe_ground(S/A/B/C) = 左侧尺：问"这位置跌不跌得下去、有没有底可托、抗不抗摔"。用它做持仓/抗跌评估。
  两者无关：一只票可以"左侧无垫还在跌"(C) 但"右侧若反转空间大"；也可能已涨到高位(右侧A)而"左侧已无垫、下跌空间大开"。
  同一只票两个维度分开看，各问各的。→ 这正是"不同案例不同分析"。

统一口径：
  · 日线 MA55/MA233、MACD(12,26,9)，强弱按 DIF/DEA 相对0轴；
  · 周线也用同一套算 zone（看大级别是站上0轴、还是仍泡在0轴下）；
  · 历史低位百分位 perc：(现价-近N年周K最低)/(近N年周K最高-最低)，
    越接近0=越低(离底部成本越近)，越接近1=越高(已涨上去、离山腰/峰越近)。
  · 抗跌档位（给持仓的一句结论）：
      [厚垫S] 低位企稳：已在历史低区 + 价站回55上方(周也倾向0轴上)
               ↓ 下面就是真实底部密集区，抗跌最好、第二只脚来了相对浅跌能接回。
      [有垫A] 企稳但不高不低：站回55上方 + 但历史位置中等(一段涨幅已兑现)
               ↓ 有垫但离安全底还有距离；能扛反复但别指望"深跌"。
      [浅垫B] 半垫/在企稳边缘：已站回价格贴/居55上沿，但周线还没翻0轴
               ↓ 价上了55算过半垫，可还不扎实，破55就是它松动要撤的点。
      [无垫C] 仍在下降通道：价在55下方(无论历史位置多低)。底未确认，只有等放量站回55才谈得上见底。
      ↑ 重要纪律：看跌不跌得下去，"历史百分位低(超跌/创新低)"绝不等于"见底"，
        不能把"跌得多"当作"跌不动"。判别只认量价企稳：(1)不再创新低 (2)放量/转绿站回55上方
        (3)周线脱离0轴下。三者未齐，一律按 C(下降通道、底未确认)对待，别当底。高位的另+谨防回踩。
"""
from __future__ import annotations

import pandas as pd

from strategy.main_wave import macd_df, zone  # 复用均线/MACD/强弱区计算


# ---- 阈值统一从 config 读（config.SAFE_GROUND_RULE）----
_T = {  # 兜底值（config 若没配可用）；真值以 config 为准
    "years_perc": 3,      # 计算历史低位百分位用的回看年数
    "perc_low": 0.35,     # perc <= 此值视"历史低位"(离底近)
    "perc_high": 0.75,    # perc >= 此值视"历史高位区"(离底远、需防回踩)
    "gap55_buy": 0.10,    # 判定"贴55线企稳上沿"的袋宽(±10%)宽度参考
}


def _conf(cfg=None):
    if cfg is None:
        return _T
    d = dict(_T)
    d.update(getattr(cfg, "SAFE_GROUND_RULE", {}))
    return d


def evaluate(code, ds, cfg=None):
    """对一只票返回左侧安全垫判档 dict（真实拉日线/周K计算）。"""
    t = _conf(cfg)
    years = t["years_perc"]
    day = ds._fetch_ohlcv(code, interval="1d",
                          start_ms=int((__import__("time").time() - years * 366 * 86400) * 1000))
    wk = ds.get_kline(code, interval="1w", days=years * 400)
    if day is None or wk is None or day.empty or wk.empty:
        return {"code": code, "grade": None, "note": "数据不足"}
    day = macd_df(day.sort_values("date").reset_index(drop=True))
    wk = macd_df(wk.sort_values("date").reset_index(drop=True))
    dl, wl = day.iloc[-1], wk.iloc[-1]
    if pd.isna(dl["ma55"]) or pd.isna(dl["ma233"]):
        return {"code": code, "grade": None, "note": "均线不足"}

    price = float(dl["close"])
    gap55 = (price - float(dl["ma55"])) / float(dl["ma55"])
    d_zone = zone(dl["dif"], dl["dea"])
    w_zone = zone(wl["dif"], wl["dea"])
    w_on = w_zone.startswith("强") or w_zone.startswith("极强")   # 周站0轴上
    # 历史低位百分位（近 years 年 周K收盘）
    weekly_c = wk["close"].dropna()
    lo, hi = float(weekly_c.min()), float(weekly_c.max())
    perc = float((price - lo) / (hi - lo)) if hi > lo else 0.0

    below55 = gap55 < 0
    # ---- 抗跌档位（左侧）----
    if w_on and not below55:
        if perc <= t["perc_low"]:
            grade, note = "S", "厚垫·低位企稳：历史低区 + 站回55上方，下面有真实底，抗跌最好"
        elif perc <= t["perc_high"]:
            grade, note = "A", "有垫·企稳中段：站回55上方但历史位置中等，能扛反复、别指望深跌接回"
        else:
            grade, note = "B", "已涨偏高·需防回踩：在上50~已离底远，若追高二脚下来跌得比低位的快"
    elif not below55 and not w_on:
        grade, note = "B", "半垫·周还没翻0轴上：站上55且大级别未坐实，破55要撤"
    # ---- 关键(否则会误导)：50轴下的票只要还在55线下方＝下降通道的“底未确认”。
    #      历史百分位低(超跌/创新低)≠见底，绝不能用“跌得多所以跌不动”去当垫；
    #      底要等放量企稳(价站回55上方/不再创新低/转绿)才算。故此类一律 C。
    elif below55:
        grade, note = "C", ("无垫·仍在下降通道：价在55线下、量价未确认企稳，底在哪没人能预判——"
                            "不是凭位置低就能当底仓，须等放量站回55线/止跌后再谈")
    else:
        grade, note = "B", "需盯"

    if perc >= t["perc_high"]:
        trailer = "　【注意已达历史高位区，右侧再热都不追二脚回踩】"
    else:
        trailer = ""
    return {
        "code": code,
        "name": _name_of(code, ds),
        "grade": grade,
        "price": price, "ma55": float(dl["ma55"]), "ma233": float(dl["ma233"]),
        "gap55": gap55, "perc": perc,
        "日": d_zone, "周": w_zone,
        "note": note,
        "wait": _advice(grade) + trailer,
    }


def _advice(grade):
    if grade == "S":
        return "拿得住：下有底盘整，第二只脚若来是相对抗跌块，破下方底/跌破55再减"
    if grade == "A":
        return "可持有：不指望它抗深跌，破55/成本线分批减，别当避险拿"
    if grade == "B":
        return "盯：半垫或偏高位，破55(或贴55下沿)果断减，别赌它硬扛指数"
    if grade == "C":
        return "慎重：无垫仍在降通道，企稳(站回55+0轴)前不加，破成本先撤"
    return "—"


def _name_of(code, ds):
    """给 code 一个可读名字；失败回退代号。"""
    try:
        q = ds.get_stock_quote(code)
        nm = getattr(q, "name", None)
        return nm if nm else code
    except Exception:
        return code


def _name_map(codes, ds):
    """尽力取诚实名字：仅采纳 ticker 与查询码一致且资产为股票的名称，否则保留代号。"""
    m = {}
    try:
        for c in set(codes):
            d = ds._get("/api/meta/tickers/search", {"q": c, "limit": 6})
            it = (d or {}).get("item") or []
            hit = None
            for row in it:
                is_stock = (row.get("asset_type") or "").find("a-share") >= 0
                if row.get("ticker") == c and is_stock:
                    hit = row.get("name") or c
                    break
            m[c] = hit or c
    except Exception:
        pass
    return m


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from config import Config
    from data_source.base import get_data_source

    codes = sys.argv[1:] or ["300033", "002241"]
    cfg = Config(); ds = get_data_source(cfg)
    try:
        ds.connect()
        names = _name_map(codes, ds)
        # 用真正的名字优先覆盖数值代号(减少展示歧义)
        for c in codes:
            try:
                r = evaluate(c, ds, cfg)
            except Exception as e:
                print("=" * 70)
                print(f"[{c}] 判读中断: {str(e)[:80]}")
                continue
            print("=" * 70)
            if not r.get("grade"):
                print(f"[{c}]({names.get(c,'')}) {r['note']}")
                continue
            nm = names.get(c, r.get('name', c))
            print(f"[{c}] {nm}  抗跌等级={r['grade']}   现价≈{r['price']:.2f}")
            print(f"   在55线 {r['gap55']*100:+.1f}% (55={r['ma55']:.2f} / 233={r['ma233']:.2f})  "
                  f"历史低位百分位={r['perc']:.2f}")
            print(f"   日={r['日']} | 周={r['周']}")
            print(f"   判读: {r['note']}")
            print(f"   该做: {r['wait']}")
    finally:
        ds.close()
