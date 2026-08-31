"""基础过滤策略：价格、流动性等硬性条件，同时处理排除代码规则。"""
from __future__ import annotations

import fnmatch
from typing import List

from data_source.base import StockData
from .base import BaseStrategy


class BasicFilter(BaseStrategy):
    """对股票池做基础过滤。"""

    def filter(self, stocks: List[StockData]) -> List[StockData]:
        rule = self._cfg.BASIC_FILTER
        excludes = self._cfg.EXCLUDE_CODES

        result = []
        for sd in stocks:
            # 排除代码（支持通配符）
            if any(fnmatch.fnmatch(sd.code, pat) or fnmatch.fnmatch(sd.code, pat.lower())
                   for pat in excludes):
                self._log(sd, f"命中排除规则 {excludes}")
                continue

            # 价格区间
            if sd.price < rule["min_price"] or sd.price > rule["max_price"]:
                self._log(sd, f"价格 {sd.price} 不在 [{rule['min_price']},{rule['max_price']}]")
                continue

            # 成交额下限
            if sd.amount < rule["min_amount"]:
                self._log(sd, f"成交额 {sd.amount:.0f} 低于 {rule['min_amount']}")
                continue

            result.append(sd)
        return result

    @staticmethod
    def _log(sd: StockData, reason: str) -> None:
        print(f"  [BasicFilter] 剔除 {sd.code}({sd.name}): {reason}")
