# -*- coding: utf-8 -*-
"""推演：某价(或其平台上)须维持多久，MA55 才会重新上穿 MA233(55对233金叉)。
用真实历史收盘 + 前向模拟(未来逐日加入假设价格)，供判断某下降/弱势标的离
"55重上233金叉"还差多远 / 需要站住哪个平台。只求几何传导，不做买卖建议。
用法: python scripts/project_ma_cross.py 002230 [39.5 41.5 44 46 48 ...]
  （第二个参数起 = 若干待测的"横盘/平台价"；不传则给一组默认平台价）
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import Config
from data_source.base import get_data_source


def main():
    code = sys.argv[1]
    levels = [float(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else None
    cfg = Config()
    ds = get_data_source(cfg)
    try:
        ds.connect()
        df = ds._fetch_ohlcv(
            code, interval="1d",
            start_ms=int(pd.Timestamp("2022-01-01").timestamp() * 1000),
        )
        if df is None or df.empty:
            print("无数据")
            return
        df = df.sort_values("date").reset_index(drop=True)
        c = df["close"]
        m55 = c.rolling(55).mean()
        m233 = c.rolling(233).mean()
        lo = df.iloc[-1]
        price = float(lo["close"])
        last55 = float(m55.iloc[-1])
        last233 = float(m233.iloc[-1]) if not pd.isna(m233.iloc[-1]) else float("nan")
        print(f"标的 {code}  最新 {lo['date'].date()}  收 {price:.2f}")
        print(f"  MA55 = {last55:.2f}  (价/55 = {(price-last55)/last55*100:+.1f}%)")
        if not np.isnan(last233):
            state23 = "已在MA55下方" if last55 > last233 else "MA55仍在MA233之下(空头排列倒挂)"
            print(f"  MA233= {last233:.2f}  (55/233 = {(last55-last233)/last233*100:+.1f}%) → {state23}")
        hist = c.to_numpy()

        def cross_after(level, max_days=800):
            ext = list(hist)
            for k in range(1, max_days + 1):
                ext.append(level)
                a = np.asarray(ext, dtype=float)
                m5 = a[-55:].mean()
                m2 = a[-233:].mean()
                if m5 > m2:
                    return k, float(m5), float(m2)
            return None, None, None

        # 默认候选平台价：现价 / 55线附近 / MA233下方几档
        if levels is None:
            _base = sorted({price, last55, round((last55 + 2), 2),
                            44.0, 46.0, 20.0})
            levels = [x for x in _base if x > 0]
        print("\n—— 前向模拟(假设价格在某平台横住，MA55要多久重新上穿MA233) ——")
        print(f"{'平台价':>8}  {'相对55':>8}  {'金叉需天数':>10}   {'届时MA55':>9} {'届时MA233':>9}")
        for p in levels:
            need, m5, m2 = cross_after(p)
            gap5 = (p - last55) / last55 * 100
            if need is None:
                print(f"{p:8.2f}  {gap5:+7.1f}%  {('>800 or never'):>10}")
            else:
                print(f"{p:8.2f}  {gap5:+7.1f}%  {need:>10}   {m5:9.2f} {m2:9.2f}")
        print("\n注：横在越低，MA55需越久才可能把倒挂拉平/上穿；"
              "且中间若再现下跌会重新延后。这只给几何门槛，不是预测。")
    finally:
        ds.close()


if __name__ == "__main__":
    main()

