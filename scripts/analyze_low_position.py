"""对精选集合（持仓/自选/观察）运行低位判断策略（历史百分位法）。

用法：
    python scripts/analyze_low_position.py [集合]
    集合: holdings | watchlist | observation | all   (默认 all)

说明：低位策略需要拉每只股票多年历史数据，因此这里只针对所选
集合（通常十余只）计算，避免全市场扫描产生大量请求。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from data_source.base import get_data_source, StockData
from strategy.low_position import LowPositionStrategy


def resolve_codes(cfg, key: str) -> list:
    attr_map = {
        "holdings": "HOLDINGS",
        "watchlist": "WATCHLIST",
        "observation": "OBSERVATION",
    }
    return getattr(cfg, attr_map[key], [])


def main():
    parser = argparse.ArgumentParser(description="对集合运行低位判断策略")
    parser.add_argument("collection", nargs="?", default="all")
    args = parser.parse_args()

    cfg = Config()
    if cfg.DATA_SOURCE != "hithink":
        print("请设置 DATA_SOURCE=hithink 使用同花顺官方数据。")
        return
    ds = get_data_source(cfg)
    if not ds.connect():
        print("连接失败")
        return

    strat = LowPositionStrategy(cfg, ds)
    try:
        keys = ["holdings", "watchlist", "observation"]
        selected = keys if args.collection == "all" else [args.collection]
        for key in selected:
            if key not in keys:
                print(f"未知集合: {key}，可选 {keys} 或 all")
                continue
            items = resolve_codes(cfg, key)
            label = cfg.COLLECTIONS.get(key, key)
            print(f"\n========== {label}（{len(items)} 只）===========")
            stocks = []
            for it in items:
                sd = ds.get_stock_quote(it["code"])
                if sd is None:
                    print(f"  {it['code']}: 无行情，跳过")
                    continue
                sd.name = it.get("name") or sd.name
                stocks.append(sd)

            # 跑低位策略
            keeper = strat.filter(stocks)
            print(f"  -> 处于低位: {len(keeper)} 只")
            for k in keeper:
                print(f"     命中: {k.code} {k.name}")
    finally:
        ds.close()


if __name__ == "__main__":
    main()
