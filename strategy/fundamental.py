"""基本面策略：按 PE / ROE 等财务指标筛选。"""
from __future__ import annotations

from typing import List

from data_source.base import StockData
from .base import BaseStrategy


class FundamentalStrategy(BaseStrategy):
    """按市盈率区间与净资产收益率筛选。"""

    def filter(self, stocks: List[StockData]) -> List[StockData]:
        rule = self._cfg.FUNDAMENTAL_RULE
        min_pe, max_pe = rule["min_pe"], rule["max_pe"]
        min_roe = rule["min_roe"]

        result = []
        for sd in stocks:
            fd = self._ds.get_fundamentals(sd.code)
            pe = fd.pe
            roe = fd.roe
            if pe is None or roe is None:
                print(f"  [Fundamental] 跳过 {sd.code}({sd.name}): 缺少财务数据")
                continue
            if not (min_pe <= pe <= max_pe):
                print(f"  [Fundamental] 剔除 {sd.code}({sd.name}): PE={pe} 不在区间")
                continue
            if roe < min_roe:
                print(f"  [Fundamental] 剔除 {sd.code}({sd.name}): ROE={roe:.2%} < {min_roe:.2%}")
                continue
            # 通过筛选，把基本面数据回填到原对象，便于最终输出
            sd.pe = pe
            sd.roe = roe
            result.append(sd)
        return result
