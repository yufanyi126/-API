# -*- coding: utf-8 -*-
"""历史(2020起)回放某票 某时段的 周K末端均线/MACD 快照。
用法: python scripts/hist_timeline.py 600030 2024-01-01 2025-03-31
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
import pandas as pd
from config import Config
from data_source.base import get_data_source


def load_long(code):
    cfg = Config(); ds = get_data_source(cfg)
    try:
        ds.connect()
        df = ds._fetch_ohlcv(code, interval="1d", start_ms=1577836800000)  # 2020
        return df
    finally:
        ds.close()


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "600030"
    d0 = sys.argv[2] if len(sys.argv) > 2 else "2023-01-01"
    d1 = sys.argv[3] if len(sys.argv) > 3 else "2025-06-30"
    df = load_long(code)
    if df is None or df.empty:
        print("no data"); return
    df = df.sort_values("date").reset_index(drop=True)
    c = df["close"]
    ema_f = c.ewm(span=12, adjust=False).mean()
    ema_s = c.ewm(span=26, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=9).mean()
    hist = (dif - dea) * 2
    df = df.assign(ma55=c.rolling(55).mean(), ma233=c.rolling(233).mean(),
                   dif=dif, dea=dea, hist=hist)
    sub = df[(df["date"] >= pd.Timestamp(d0)) & (df["date"] <= pd.Timestamp(d1))].copy()
    sub["yw"] = sub["date"].dt.to_period("W")
    sub = sub.groupby("yw", as_index=False).tail(1)
    print(f"板块内标的 {code}  周K末端快照 {d0}~{d1}  (MA55/MA233 用日线前复权算)")
    print(f"{'周截至':<12}{'收盘':>9}{'MA55':>8}{'MA233':>8}{'DIF':>7}{'DEA':>7}"
          f"  柱  价-55%")
    for _, r in sub.iterrows():
        if pd.isna(r["ma55"]) or pd.isna(r["ma233"]):
            continue
        gap = (r["close"] - r["ma55"]) / r["ma55"] * 100
        print(f"{str(r['date'].date()):<12}{r['close']:9.2f}{r['ma55']:8.2f}"
              f"{r['ma233']:8.2f}{r['dif']:7.2f}{r['dea']:7.2f}"
              f"  {'红' if r['hist']>0 else '绿'}  {gap:+.1f}%")


if __name__ == "__main__":
    main()
