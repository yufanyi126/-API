# -*- coding: utf-8 -*-
"""回放某只股票历史某个时段的均线/MACD快照，验证当时的形态档位。
用法: python scripts/backtest_snapshot.py 600030 2024-07-01 2024-11-10
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
import datetime as dt
import pandas as pd
from config import Config
from data_source.base import get_data_source


def macd(cc):
    ema_f = cc.ewm(span=12, adjust=False).mean()
    ema_s = cc.ewm(span=26, adjust=False).mean()
    d = ema_f - ema_s
    de = ema(d, 9)
    h = (d - de) * 2
    return d, de, h

def ema(s, w): return s.ewm(span=w, adjust=False).mean()


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "600030"
    d0 = sys.argv[2] if len(sys.argv) > 2 else "2024-07-01"
    d1 = sys.argv[3] if len(sys.argv) > 3 else "2024-11-10"
    cfg = Config(); ds = get_data_source(cfg)
    try:
        ds.connect()
        df = ds.get_daily_bars(code, years=4)
        if df is None or df.empty:
            print("no data"); return
        df = df.sort_values("date").reset_index(drop=True)
        c = df["close"]
        dif, dea, hist = macd(c)
        df = df.assign(ma55=c.rolling(55).mean(), ma233=c.rolling(233).mean(),
                       dif=dif, dea=dea, hist=hist)
        sub = df[(df["date"] >= pd.Timestamp(d0)) & (df["date"] <= pd.Timestamp(d1))]
        print(f"标的 {code}  观察段 {d0} ~ {d1}")
        print(f"{'日期':<12}{'收盘':>8}{'MA55':>8}{'MA233':>8}{'DIF':>7}{'DEA':>7}  柱  距55%")
        for _, r in sub.iterrows():
            if pd.isna(r["ma55"]):
                continue
            gap = (r["close"] - r["ma55"]) / r["ma55"] * 100
            print(f"{str(r['date'].date()):<12}{r['close']:8.2f}{r['ma55']:8.2f}"
                  f"{r['ma233']:8.2f}{r['dif']:7.2f}{r['dea']:7.2f}"
                  f"  {'红' if r['hist']>0 else '绿'}  {gap:+.1f}%")
    finally:
        ds.close()

if __name__ == "__main__":
    main()
