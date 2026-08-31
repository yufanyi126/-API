"""模拟数据源：为框架开发/调试提供假数据，不依赖任何外部 API。

在没有连接同花顺客户端或官方 dll 的情况下，可以用它跑通整个策略流程。
"""
from __future__ import annotations

import random
from typing import List, Optional

import pandas as pd

from .base import DataSourceBase, StockData

random.seed(42)

_MOCK_CODES = [
    ("600000", "浦发银行"), ("600519", "贵州茅台"), ("000001", "平安银行"),
    ("000002", "万科A"), ("600036", "招商银行"), ("000333", "美的集团"),
    ("601318", "中国平安"), ("600030", "中信证券"), ("000858", "五粮液"),
    ("002415", "海康威视"),
]


class MockDataSource(DataSourceBase):
    """返回伪随机行情与基本面的模拟数据源。"""

    def connect(self) -> bool:
        return True

    def get_stock_pool(self, market: str = "沪深A股") -> List[str]:
        return [c for c, _ in _MOCK_CODES]

    def get_stock_quote(self, code: str) -> Optional[StockData]:
        row = next((x for x in _MOCK_CODES if x[0] == code), None)
        if not row:
            return None
        price = round(random.uniform(5, 150), 2)
        return StockData(
            code=code,
            name=row[1],
            price=price,
            change_pct=round(random.uniform(-6, 6), 2),
            amount=round(random.uniform(1e7, 5e9)),
        )

    def get_history(self, code: str, days: int = 60) -> Optional[pd.Series]:
        base = random.uniform(5, 150)
        vals = [base * (1 + 0.004 * i + random.uniform(-0.02, 0.02)) for i in range(days)]
        idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days)
        return pd.Series(vals, index=idx, name="close")

    def get_fundamentals(self, code: str) -> StockData:
        sd = self.get_stock_quote(code)
        if sd is None:
            return StockData(code=code)
        sd.pe = round(random.uniform(5, 60), 2)
        sd.roe = round(random.uniform(0.05, 0.30), 3)
        return sd
