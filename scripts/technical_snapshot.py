# -*- coding: utf-8 -*-
"""用同花顺数据源拉真实日K，判断均线55/233 与 MACD 时空状态。

用法: python scripts/technical_snapshot.py [code] [years]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd

from config import Config
from data_source.base import get_data_source


def macd(close, fast=12, slow=26, signal=9):
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = (dif - dea) * 2
    return dif, dea, hist


def main():
    cfg = Config()
    ds = get_data_source(cfg)
    try:
        if not ds.connect():
            print("连接失败")
            return
        code = sys.argv[1] if len(sys.argv) > 1 else "300750"
        years = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
        df = ds.get_daily_bars(code, years=years)
        if df is None or df.empty:
            print("无数据:", code)
            return

        close = df["close"]
        ma55 = close.rolling(55).mean()
        ma233 = close.rolling(233).mean()
        dif, dea, hist = macd(close)
        df = pd.DataFrame({
            "date": df["date"], "close": close,
            "ma55": ma55, "ma233": ma233,
            "dif": dif, "dea": dea, "hist": hist,
        }).dropna()

        if df.empty:
            print("数据不足")
            return

        last = df.iloc[-1]
        pr = last["close"]
        m55 = last["ma55"]
        m233 = last["ma233"]

        print("=" * 60)
        print(f"标的: {code}   最新收盘(前复权): {pr:.2f}  ({last['date'].date()})")
        print(f"MA55 ≈ {m55:.2f}   (现价相对): {(pr-m55)/m55*100:+.1f}%  "
              f"{'价格在55线上方' if pr>m55 else '价格在55线下方'}")
        print(f"MA233≈ {m233:.2f}  (现价相对): {(pr-m233)/m233*100:+.1f}%  "
              f"{'价格在233线上方' if pr>m233 else '价格在233线下方'}")
        print(f"MACD: DIF={last['dif']:+.2f}  DEA={last['dea']:+.2f}  "
              f"柱体={'红柱' if last['hist']>0 else '绿柱'}  强度≈{abs(last['hist']):.2f}")
        print("-" * 60)

        d, e = last["dif"], last["dea"]
        bull = d > e
        red = last["hist"] > 0
        if d > 0 and e > 0 and bull:
            state = "多头强区(红柱) → 中偏强/强；红柱放大可持续持仓"
        elif d > 0 >= e:
            state = "极强孕育期(DIF已上0轴、DEA待上穿) → 若红柱持续=极强"
        elif d < 0 <= e:
            state = "高位转弱(DIF已下0轴、DEA仍上方) → 弱势/中偏弱，警惕"
        elif d < 0 and e < 0 and not bull:
            state = "空头弱区(绿柱) → 弱/极弱；不做结构判断，只等55线企稳"
        else:
            state = "0轴临界/纠缠，方向未定"
        print("时空状态(日线、按MACD快慢线相对0轴):")
        print(f"  DIF>DEA(多头)? {'是' if bull else '否'}   红柱? {'是' if red else '否'}")
        print(f"  ⇒ {state}")
        print("-" * 60)

        events = []
        for i in range(2, len(df)):
            od, oe = df['dif'].iloc[i-1], df['dea'].iloc[i-1]
            nd, ne = df['dif'].iloc[i], df['dea'].iloc[i]
            date = df['date'].iloc[i]
            if nd > ne and od <= oe:
                events.append((date, "金叉(多头)", nd, ne))
            elif nd < ne and od >= oe:
                events.append((date, "死叉(空头)", nd, ne))
            if (od <= 0 < nd) or (od >= 0 > nd):
                tag = "DIF上穿0轴" if nd > 0 else "DIF下穿0轴"
                events.append((date, tag, nd, ne))
        ev = pd.DataFrame(events, columns=["date", "event", "dif", "dea"])
        if not ev.empty:
            print("金叉/死叉/0轴穿越 时间线(最近8个):")
            for _, r in ev.tail(8).iterrows():
                print(f"  {r['date'].date()}  {r['event']}  dif={r['dif']:+.2f} dea={r['dea']:+.2f}")
            last_stop = ev['date'].iloc[-1]
            bars_since = int((df['date'] > last_stop).sum())
            print(f"\n最近一次事件: {ev['event'].iloc[-1]}  {last_stop.date()}  (距今{bars_since}个交易日)")
            # 最近N=最近3 根是否在持续红柱/绿柱
    finally:
        ds.close()


if __name__ == "__main__":
    main()
