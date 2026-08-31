"""选股流水线：串联【取数据 -> 各策略 -> 输出】全流程。"""
from __future__ import annotations

from typing import List

from config import Config
from data_source.base import DataSourceBase, StockData, get_data_source
from strategy import (
    BasicFilter,
    FundamentalStrategy,
    MomentumStrategy,
    LowPositionStrategy,
    VolumeDivergenceStrategy,
)
class StockSelectionPipeline:
    """把数据源与各策略按顺序串起来执行。"""

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._ds: DataSourceBase = get_data_source(cfg)

    def run(self) -> List[StockData]:
        # 1. 连接数据源
        if not self._ds.connect():
            raise RuntimeError("数据源连接失败，请检查同花顺客户端或网络。")
        try:
            # 2. 获取股票池
            pool_codes = self._ds.get_stock_pool()
            print(f"共拉取候选股票 {len(pool_codes)} 只")

            # 3. 拉取每只股票的快照
            stocks = []
            for code in pool_codes:
                quote = self._ds.get_stock_quote(code)
                if quote is not None:
                    stocks.append(quote)

            # 4. 依次执行各策略（链式过滤）
            enabled = self._cfg.ENABLE_FILTERS
            stages = [
                ("basic", BasicFilter(self._cfg, self._ds)),
                ("momentum", MomentumStrategy(self._cfg, self._ds)),
                ("fundamental", FundamentalStrategy(self._cfg, self._ds)),
                ("low_position", LowPositionStrategy(self._cfg, self._ds)),
                ("volume_divergence", VolumeDivergenceStrategy(self._cfg, self._ds)),
            ]

            result = stocks
            for key, stage in stages:
                if enabled.get(key, False):
                    before = len(result)
                    result = stage.filter(result)
                    print(f"策略 {stage.name()}: {before} -> {len(result)} 只")

            return result
        finally:
            self._ds.close()

