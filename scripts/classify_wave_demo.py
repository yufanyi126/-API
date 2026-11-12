# -*- coding: utf-8 -*-
"""验证 main_wave 档位规则：对若干标的按真实数据归类 A/B/C。
用法: python scripts/classify_wave_demo.py code1 code2 ...
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
import pandas as pd
from config import Config
from data_source.base import get_data_source
from strategy.main_wave import macd_df, zone, classify_single, describe


def main():
    codes = sys.argv[1:] or ["600519", "002241", "000506", "600988",
                             "300454", "600030", "300033", "601108"]
    cfg = Config(); ds = get_data_source(cfg)
    try:
        ds.connect()
        for code in codes:
            day = ds._fetch_ohlcv(code, interval="1d", start_ms=1577836800000)
            wk = ds.get_kline(code, interval="1w", days=280*7)
            if day is None or wk is None or day.empty or wk.empty:
                print(f"[{code}] 数据不足"); continue
            day = day.sort_values("date").reset_index(drop=True)
            wk = wk.sort_values("date").reset_index(drop=True)
            day = macd_df(day); wk = macd_df(wk)
            dl, wl = day.iloc[-1], wk.iloc[-1]
            if pd.isna(dl["ma55"]) or pd.isna(wl["dif"]):
                print(f"[{code}] warming(前段不足)"); continue
            day_zone = zone(dl["dif"], dl["dea"])
            week_zone = zone(wl["dif"], wl["dea"])
            gap55 = (dl["close"] - dl["ma55"]) / dl["ma55"]
            describe(code, week_zone, day_zone, gap55)
    finally:
        ds.close()


if __name__ == "__main__":
    main()
