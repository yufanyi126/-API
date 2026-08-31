"""分析某只股票今年逐平台期（阶段）的平均成交量。

复用了带本地缓存的 get_daily_bars（与股价同一份缓存，不重复请求）。

"平台期"按两种口径划分：
  1. 月度平台：把今年按自然月切分，统计每月平均日成交量。
  2. 横盘识别：基于"价格波动幅度小"识别横盘整理段（可选）。

年份默认取当前系统时间所在年份，例如系统时间是 2026-08，则分析 2026 年。

用法：
    python scripts/analyze_platform_volume.py 002241 [--year 2026]
"""
import argparse
import datetime as dtm
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from data_source.base import get_data_source


def main():
    parser = argparse.ArgumentParser(description="分析个股今年分段平均成交量")
    parser.add_argument("code", help="6 位股票代码，如 002241")
    parser.add_argument("--year", type=int, default=None,
                        help="分析年份（默认取当前系统时间所在年份）")
    args = parser.parse_args()

    cfg = Config()
    if cfg.DATA_SOURCE != "hithink":
        print("请设置 DATA_SOURCE=hithink 使用同花顺官方数据。")
        return
    ds = get_data_source(cfg)
    if not ds.connect():
        print("连接失败")
        return

    try:
        # 年份默认以系统时间为准
        year = args.year or dtm.datetime.now().year
        # 拉足够多年的日线（含成交量），走本地缓存
        df = ds.get_daily_bars(args.code, years=5)
        if df is None or df.empty:
            print("未取到数据，请检查代码。")
            return

        # 只取目标年份的数据
        df = df[df["date"].dt.year == year].copy()
        if df.empty:
            print(f"缓存中没有 {year} 年数据。")
            return

        print(f"\n歌尔股份({args.code}) {year}年日K数据 {len(df)} 个交易日"
              f"  [{df['date'].min().date()} ~ {df['date'].max().date()}]")

        # ---- 1. 月度平台 ----
        df["month"] = df["date"].dt.to_period("M")
        print("\n=== 按月平均成交量（单位：万股/日）===")
        monthly = df.groupby("month")["volume"].agg(["mean", "median", "sum", "count"])
        monthly = monthly.rename(columns={"mean": "平均成交量",
                                          "median": "中位成交量",
                                          "sum": "当月总量",
                                          "count": "交易日数"})
        for m, row in monthly.iterrows():
            print(f"  {m}  平均={row['平均成交量']/1e4:10.0f}万股  "
                  f"中位={row['中位成交量']/1e4:10.0f}万股  "
                  f"当月总量={row['当月总量']/1e8:.1f}亿股  天数={int(row['交易日数']):3d}")

        # ---- 2. 横盘平台识别 ----
        print("\n=== 横盘平台识别（近 N 日价格波动 < 阈值 视为平台）===")
        n = 20
        threshold = 0.10
        df["high_roll"] = df["high"].rolling(n, min_periods=n).max()
        df["low_roll"] = df["low"].rolling(n, min_periods=n).min()
        df["swing"] = (df["high_roll"] - df["low_roll"]) / df["low_roll"]

        in_platform = df["swing"] < threshold
        segments = []
        cur = None
        for i, (_, row) in enumerate(df.iterrows()):
            if in_platform.iloc[i]:
                cur = [row["date"]] if cur is None else cur + [row["date"]]
            else:
                if cur is not None and len(cur) >= n:
                    segments.append((cur[0], cur[-1]))
                cur = None
        if cur is not None and len(cur) >= n:
            segments.append((cur[0], cur[-1]))

        if not segments:
            print("  未识别到明显的横盘平台期。")
        else:
            for s0, s1 in segments:
                seg = df[(df["date"] >= s0) & (df["date"] <= s1)]
                avg_v = seg["volume"].mean()
                pct = (seg["close"].iloc[-1] / seg["close"].iloc[0] - 1) * 100
                print(f"  {s0.date()} ~ {s1.date()}  ({(s1-s0).days}天)   "
                      f"平台内涨跌={pct:+.2f}%  日均成交量={avg_v/1e4:.0f}万股")

        out = os.path.join("results", f"{args.code}_platform_volume_{year}.csv")
        os.makedirs("results", exist_ok=True)
        monthly.to_csv(out, encoding="utf-8-sig", float_format="%.0f")
        print(f"\n月度成交量明细已保存: {out}")
    finally:
        ds.close()


if __name__ == "__main__":
    main()
