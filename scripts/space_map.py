# -*- coding: utf-8 -*-
"""打印某票历史上方各档压力位/前高 + 黄金分割位，生成"空间目标地图"。
用法: python scripts/space_map.py 002241
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
import pandas as pd
import numpy as np

from config import Config
from data_source.base import get_data_source


def swing_highs(df, window=40):
    """在收盘/最高序列里找局部高点（左窗+右窗都比它小者）. 返回 (idx, price)"""
    highs = df["high"].values
    n = len(highs)
    pts = []
    for i in range(window, n - window):
        seg = highs[i-window:i+window+1]
        if highs[i] == max(seg):
            pts.append((i, highs[i]))
    return pts


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "002241"
    cfg = Config()
    ds = get_data_source(cfg)
    try:
        if not ds.connect():
            print("连接失败"); return
        df = ds.get_daily_bars(code, years=6)
        if df is None or df.empty:
            print("无数据"); return
        df = df.sort_values("date").reset_index(drop=True)
        cur = df["close"].iloc[-1]
        low6y = df["low"].min()
        hi_all = df["high"].max()
        print("=" * 62)
        print(f"标的 {code}  现价(前复权)≈{cur:.2f}   近6年最低≈{low6y:.2f}   近6年最高≈{hi_all:.2f}")
        print("=" * 62)

        # ---- 1) 上方各档历史前高(近6年摆动高点, 取在现价上方者) ----
        print("\n▌上方历史前高/摆动高(过滤在现价上方):")
        pts = swing_highs(df, window=30)
        above = []
        for i, p in pts:
            d = df["date"].iloc[i]
            if p > cur * 1.01:
                above.append((d, p))
        # 聚到不同价档(同一价位多个高点算一个压制档)
        above.sort(key=lambda x: x[1])
        dedup = []
        for d, p in above:
            if not dedup or p - dedup[-1][1] > cur * 0.02:  # 相邻差>2%才算新档
                dedup.append((d, p))
            else:
                # 同档取更高保留
                if p > dedup[-1][1]:
                    dedup[-1] = (d, p)
        if not dedup:
            print("  (现价上方近期无明显摆动高)")
        for d, p in dedup:
            print(f"  档位≈{p:6.2f}  (出现于 {d.date()}  相对现价 {(p-cur)/cur*100:+.1f}%)")

        # ---- 2) 关键平台压制(当前箱体上沿 26~27 用最近一年上沿量) ----
        print("\n▌近期(近1.5年)最明显的水平压力平台:")
        sub = df[df["date"] >= df["date"].max() - pd.Timedelta(days=550)]
        hb = sub["high"].quantile(0.80)
        hb2 = sub["high"].quantile(0.50)
        print(f"  近1.5年最高区上沿(P80) ≈ {hb:.2f}   中位区 ≈ {hb2:.2f}")

        # ---- 3) 黄金分割(以近6年最低—最高 整段) ----
        print("\n▌黄金分割(按近6年最低→最高 全区间):")
        span = hi_all - low6y
        for label, ratio in [("0.236", 0.236), ("0.382", 0.382),
                             ("0.5", 0.5), ("0.618", 0.618),
                             ("0.786", 0.786)]:
            val = low6y + span * ratio
            mark = "   <= 现价在其上方" if cur > val else ""
            print(f"  {label}位  ≈ {val:7.2f}   ({ratio*100:.1f}%回撤/反抽点位){mark}")

        # ---- 4) 从某个阶段低点推算量度——用最近一段上行启动的锤 ----
        # 现价/近期区间的潜在中枢(供"突破那一下"之后的接力参考)
        print("\n▌空间提示:")
        if hb > cur:
            print(f"  · 第一道大闸 = {hb:.2f}（突破确立位，未站稳前空间封闭）")
            print("  · 站稳其上后，再看上面前高档逐级作为第二/第三目标(见上方列表)")
        else:
            print("  · 现价已在近期上沿之上，上方以下方前高档为主")

        # 存CSV
        import os as _os
        out = _os.path.join("results", f"{code}_space_map.csv")
        rows = [{"kind": "现价", "level": round(cur,2), "note": "current"}]
        for k, r, v in [("0.236",0.236,low6y+span*0.236),
                        ("0.382",0.382,low6y+span*0.382),
                        ("0.5",0.5,low6y+span*0.5),
                        ("0.618",0.618,low6y+span*0.618),
                        ("0.786",0.786,low6y+span*0.786)]:
            rows.append({"kind": f"仓位{k}", "level": round(v,2), "note": f"{r*100:.1f}%"})
        for i,(d,p) in enumerate(dedup,1):
            rows.append({"kind": f"历史前高#{i}", "level": round(p,2), "note": str(d.date())})
        rows.append({"kind": "近期上沿(P80)", "level": round(hb,2), "note": "1.5yr"})
        pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\n已存档: {out}")
    finally:
        ds.close()


if __name__ == "__main__":
    main()
