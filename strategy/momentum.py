"""动量策略：基于历史涨幅筛选强势股。"""
from __future__ import annotations

from typing import List

from data_source.base import StockData
from .base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """回看 N 日，要求涨幅不低于阈值。"""

    def filter(self, stocks: List[StockData]) -> List[StockData]:
        rule = self._cfg.MOMENTUM_RULE
        window = rule["window"]
        min_return = rule["min_return"]

        result = []
        for sd in stocks:
            hist = self._ds.get_history(sd.code, days=window)
            if hist is None or len(hist) < window:
                continue
            start = hist.iloc[0]
            end = hist.iloc[-1]
            if start <= 0:
                continue
            ret = (end - start) / start
            sd.history = hist
            if ret >= min_return:
                result.append(sd)
            else:
                print(f"  [Momentum] 剔除 {sd.code}({sd.name}): {window}日涨幅 {ret:.2%} < {min_return:.2%}")
        return result
