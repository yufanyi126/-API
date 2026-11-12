# -*- coding: utf-8 -*-
"""多周期判读：周K(大级别方向) + 日K(时空) + 60/15分钟(精确买点共振)。
用法:
  python scripts/snapshot_multilevel.py 002241
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
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


def time_state(dif, dea, hist, name):
    bull = dif > dea
    red = hist > 0
    if dif > 0 and dea > 0 and bull:
        s = "强区(0轴上、多头、红柱)"
    elif dif > 0 >= dea:
        s = "极强孕育(DIF已上0轴, DEA待上) "
    elif dif < 0 and dea < 0 and not bull:
        s = "弱区(0轴下、空头、绿柱)"
    elif dif < 0 <= dea:
        s = "高位转弱(DIF下0轴, DEA仍上)"
    else:
        s = "0轴临界纠缠"
    print(f"  [{name}] DIF={dif:+.3f} DEA={dea:+.3f} 柱={'红' if red else '绿'} "
          f"DIF>DEA={bull} ⇒ {s}")


def analyze_interval(ds, code, interval, days, label, title="轮"):
    """返回 DataFrame 及最新时空/均线关系 打印概览。"""
    df = ds.get_kline(code, interval=interval, days=days)
    if df is None or df.empty:
        print(f"  [{label}] 无 {interval} 数据")
        return None
    close = df["close"]
    dif, dea, hist = macd(close)
    df = df.assign(dif=dif, dea=dea, hist=hist,
                   ma55=close.rolling(55).mean(),
                   ma233=close.rolling(233).mean())
    last = df.iloc[-1]
    print(f"\n▌{label}（{interval} · {len(df)} 根，{title}） 最新收盘={last['close']:.2f} "
          f"({last['date']})")
    time_state(last["dif"], last["dea"], last["hist"], f"{label}/最新")
    for nm, col in (("MA55", "ma55"), ("MA233", "ma233")):
        v = last.get(col)
        if v is not None and pd.notna(v):
            side = "上" if last["close"] > v else "下"
            print(f"  [{label}] {nm}≈{v:.2f} → 现价在{nm}{side}  "
                  f"相对{(last['close']-v)/v*100:+.1f}%")
        else:
            print(f"  [{label}] {nm}=数据不足(K线数<233)")
    # 红柱面积方向（近5根红柱 vs 前段）
    h5 = hist.tail(5)
    rising = h5.iloc[-1] > h5.iloc[0]
    print(f"  [{label}] 近5根柱 {('红柱放大(走强)' if rising else '柱体趋弱/收口')}")
    return df


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "002241"
    cfg = Config()
    ds = get_data_source(cfg)
    try:
        if not ds.connect():
            print("连接失败"); return
        print("=" * 62)
        print(f"标的 {code}  多周期技术判读（真实数据，同花顺通道）")
        print("=" * 62)

        # 周K：看更大级别何时化解 / 是空头压制还是多头
        analyze_interval(ds, code, "1w", days=280 * 7, label="周K",
                         title="近7年周K")
        # 日K
        analyze_interval(ds, code, "1d", days=365 * 2, label="日K",
                         title="近2年日K")
    finally:
        ds.close()


if __name__ == "__main__":
    main()


