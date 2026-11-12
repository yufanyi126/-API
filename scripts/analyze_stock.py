# -*- coding: utf-8 -*-
"""单票完整技术判读（今后统一入口）。

一条命令给出：
  1) 均线 55/233 + MACD + 时空状态快照
  2) 周K(大级别) + 日K(交易级别) 跨级共振判读
  3) 上方空间目标图(前高/黄金分割/平台压制)，并落盘 CSV

用法:
  python scripts/analyze_stock.py <代码6位>      # 例: 002241
数据: HITHINK 同花顺官方通道(真实历史K线)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
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


def time_state(dif, dea, hist):
    bull = dif > dea
    red = hist > 0
    if dif > 0 and dea > 0:
        return "强区(0轴上方)"
    if dif > 0 >= dea:
        return "极强孕育(DIF上0轴,DEA待上)"
    if dif < 0 < dea:
        return "高位转弱(DIF下0轴)"
    if dif < 0 and dea < 0:
        return "弱区(0轴下方)"
    return "0轴临界纠缠"


def swing_highs(df, window=30):
    highs = df["high"].values
    n = len(highs)
    pts = []
    for i in range(window, n - window):
        if highs[i] == max(highs[i-window:i+window+1]):
            pts.append((df["date"].iloc[i], highs[i]))
    return pts


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    code = sys.argv[1]
    cfg = Config()
    ds = get_data_source(cfg)
    try:
        if not ds.connect():
            print("连接失败"); return

        # ========= ① 日线 55/233 + 时空 =========
        daily = ds.get_daily_bars(code, years=2)
        if daily is None or daily.empty:
            print("无日线数据"); return
        daily = daily.sort_values("date").reset_index(drop=True)
        c = daily["close"]
        d = daily.assign(ma55=c.rolling(55).mean(), ma233=c.rolling(233).mean(),)
        dif, dea, hist = macd(c)
        d = d.assign(dif=dif, dea=dea, hist=hist)
        last = d.iloc[-1]
        print("=" * 62)
        print(f"标的 {code}  现价(前复权)≈{last['close']:.2f}  ({last['date'].date()})")
        print(f"  日K: MA55≈{last['ma55']:.2f}{'上' if last['close']>last['ma55'] else '下'}"
              f"  MA233≈{last['ma233']:.2f}{'上' if last['close']>last['ma233'] else '下'}")
        print(f"  日线时空: DIF={last['dif']:.2f} DEA={last['dea']:.2f} "
              f"柱={'红' if last['hist']>0 else '绿'}")
        print(f"  ⇒ 日线: {time_state(last['dif'] if not pd.isna(last['dif']) else 0,
                                        last['dea'] if not pd.isna(last['dea']) else 0,
                                        last['hist'] if not pd.isna(last['hist']) else 0)}")

        # ========= ② 周K(大级别) 跨级判读 =========
        wk = ds.get_kline(code, interval="1w", days=280*7)
        if wk is not None and not wk.empty:
            wk = wk.sort_values("date").reset_index(drop=True)
            cw = wk["close"]
            wdif, wdea, whist = macd(cw)
            wk = wk.assign(dif=wdif, dea=wdea, hist=whist,
                           ma55=cw.rolling(55).mean(), ma233=cw.rolling(233).mean())
            wlast = wk.iloc[-1]
            if pd.notna(wlast["dif"]) and pd.notna(wlast["dea"]):
                print(f"  周K: MA55≈{wlast['ma55']:.2f}  MA233≈{wlast['ma233']:.2f}")
                print(f"  周线时空: DIF={wlast['dif']:.2f} DEA={wlast['dea']:.2f} "
                      f"柱={'红' if wlast['hist']>0 else '绿'}")
                print(f"  ⇒ 周线: {time_state(wlast['dif'], wlast['dea'], wlast['hist'])}")
            # 共振判定
            dr = time_state(last['dif'] if not pd.isna(last['dif']) else 0,
                            last['dea'] if not pd.isna(last['dea']) else 0,
                            last['hist'] if not pd.isna(last['hist']) else 0)
            wr = time_state(wlast['dif'], wlast['dea'], wlast['hist'])
            if ("0轴上方" in dr) and ("0轴上方" in wr):
                print("  ※ 周/日共振状态: 双强区 → 中线主升线索成立")
            else:
                print("  ※ 周/日共振状态: 未完全共振 "
                      f"(周={wr} / 日={dr})")

        # ========= ③ 空间目标图 =========
        long_ = ds.get_daily_bars(code, years=6)
        if long_ is not None and not long_.empty:
            L = long_.sort_values("date").reset_index(drop=True)
            cur = L["close"].iloc[-1]
            low = L["low"].min(); hi = L["high"].max(); span = hi - low
            print("\n▌上方空间目标图(相对当前现价):")
            pts = swing_highs(L)
            above = sorted({round(p,1) for _, p in pts if p > cur*1.01})
            print("  · 历史前高档:")
            for p in above:
                print(f"      ≈{p:6.2f}   (+{(p-cur)/cur*100:+.0f}%)")
            print("  · 黄金分割(按近6年全集 最低→最高):")
            for lab, r in [("0.382",0.382),("0.5",0.5),("0.618",0.618),("0.786",0.786)]:
                v = low + span*r
                print(f"     {lab}位 ≈{v:6.2f}   (+{(v-cur)/cur*100:+.0f}%)")
        print("\n(详细报表另存档于 results/<code>_space_map.csv)")
    finally:
        ds.close()


if __name__ == "__main__":
    main()
