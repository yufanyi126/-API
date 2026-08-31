"""查询科创板（688 开头）PE 最高的股票。

数据来源：同花顺官方金融数据服务（hithink-finance）REST API。
流程：
  1. 分页拉取全市场 A 股代码表；
  2. 筛选 688 开头的科创板股票；
  3. 批量查询每只股票的 PE_TTM（每次 ≤100，自动分批）；
  4. 按 PE 降序排序，输出前 N 名，并落盘保存。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from data_source.base import get_data_source


def main(top_n: int = 20):
    cfg = Config()

    # 确保使用官方数据源
    if cfg.DATA_SOURCE != "hithink":
        print("提示：请设置 DATA_SOURCE=hithink 以使用同花顺官方数据。")
        print(f"当前为: {cfg.DATA_SOURCE}")
        return

    ds = get_data_source(cfg)
    if not ds.connect():
        print("连接同花顺数据服务失败。")
        return

    try:
        # 1. 全市场 A 股代码
        print("拉取全市场 A 股代码表...")
        all_codes = ds.get_full_tickers()
        print(f"全市场 A 股共 {len(all_codes)} 只")

        # 2. 筛选科创板（688 开头，且非 B 股）
        star_codes = [c for c in all_codes
                      if c.startswith("688") and c.isdigit()]
        print(f"科创板（688*）共 {len(star_codes)} 只")

        # 3. 批量查估值
        print("批量查询科创板估值...")
        valuations = ds.get_valuation_batch(star_codes)

        # 4. 按 PE 降序排序
        vals = [v for v in valuations if v.pe is not None]
        vals.sort(key=lambda v: v.pe if v.pe is not None else 0, reverse=True)

        print(f"获取到有 PE 数据的科创板股票 {len(vals)} 只")
        print("\n=== 科创板 PE 最高 TOP %d ===" % min(top_n, len(vals)))
        for i, v in enumerate(vals[:top_n], 1):
            print(f"{i:2d}. {v.code} {v.name:<8s} PE_TTM={v.pe:.2f}")

        # 落盘
        import csv
        out = os.path.join("results", "star_market_pe.csv")
        os.makedirs("results", exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["rank", "code", "name", "pe_ttm"])
            for i, v in enumerate(vals, 1):
                w.writerow([i, v.code, v.name, v.pe])
        print(f"\n完整排名已保存到: {out}（共 {len(vals)} 行）")
    finally:
        ds.close()


if __name__ == "__main__":
    main()
