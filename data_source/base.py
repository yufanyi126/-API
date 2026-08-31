"""数据源抽象基类与统一数据结构。

所有具体数据源（同花顺 ths、备用 akshare、模拟 mock 等）都必须继承
DataSourceBase 并实现其中的方法。策略层只依赖本模块定义的抽象，
从而与具体 API 实现解耦，方便日后替换数据接口。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd


@dataclass
class StockData:
    """一只股票的核心行情与基本面快照，供策略层消费。"""
    code: str                    # 股票代码，如 '600000'
    name: str = ""               # 股票名称
    price: float = 0.0           # 当前价
    change_pct: float = 0.0      # 今日涨跌幅(%)
    amount: float = 0.0          # 成交额(元)
    pe: Optional[float] = None   # 市盈率
    roe: Optional[float] = None  # 净资产收益率(%)
    # 历史收盘价序列，用于动量等时间序列策略（索引为日期）
    history: Optional[pd.Series] = field(default=None)


@dataclass
class StockPool:
    """候选股票池的返回值。"""
    stocks: List[StockData]
    code_list: List[str] = field(default_factory=list)


class DataSourceBase(ABC):
    """数据源统一接口。"""

    def __init__(self, config):
        self._cfg = config

    @abstractmethod
    def connect(self) -> bool:
        """建立与数据源（如同花顺客户端）的连接，返回是否成功。"""

    @abstractmethod
    def get_stock_pool(self, market: str = "沪深A股") -> List[str]:
        """获取某市场的全部股票代码列表。"""

    @abstractmethod
    def get_stock_quote(self, code: str) -> Optional[StockData]:
        """获取单只股票的实时快照。"""

    def get_quotes_batch(self, codes: List[str]) -> List[StockData]:
        """批量获取实时快照，默认逐个调用 get_stock_quote。

        数据源若支持批量接口（如同花顺快照端点）可覆写此方法以提升性能。
        """
        result: List[StockData] = []
        for code in codes:
            sd = self.get_stock_quote(code)
            if sd is not None:
                result.append(sd)
        return result

    @abstractmethod
    def get_history(self, code: str, days: int = 60) -> Optional[pd.Series]:
        """获取单只股票的最近 N 日收盘价序列（索引为日期）。"""

    def get_daily_bars(self, code: str, years: int = 3) -> Optional[pd.DataFrame]:
        """获取某只股票近 N 年的日线 OHLCV 数据（供历史百分位类策略用）。

        返回 DataFrame，列为 [date, open, high, low, close, volume, turnover]。
        默认不实现，返回 None；需要长期历史数据的策略会据此判断"数据不足"。
        数据源（如 hithink）应覆写以返回真实数据。
        """
        return None

    def get_daily_volume(self, code: str,
                         years: int = 3) -> Optional[pd.DataFrame]:
        """获取某只股票近 N 年的日成交量/成交额数据（供成交量类分析用）。

        返回 DataFrame，列为 [date, volume, turnover]。默认复用 get_daily_bars。
        """
        df = self.get_daily_bars(code, years=years)
        if df is None or df.empty:
            return None
        cols = [c for c in ["date", "volume", "turnover"] if c in df.columns]
        return df[cols].copy()

    @abstractmethod
    def get_fundamentals(self, code: str) -> StockData:
        """获取单只股票的基本面数据（pe/roe等），返回带基础字段的 StockData。"""

    def close(self) -> None:
        """释放资源，默认空实现。"""


def get_data_source(config):
    """数据源工厂：根据 config.DATA_SOURCE 返回对应实现。"""
    source_name = config.DATA_SOURCE.lower().strip()

    if source_name == "ths":
        from .ths_source import THSDataSource
        return THSDataSource(config)
    if source_name == "hithink":
        from .hithink_source import HithinkDataSource
        return HithinkDataSource(config)
    if source_name == "akshare":
        from .akshare_source import AKShareDataSource
        return AKShareDataSource(config)
    if source_name == "mock":
        from .mock_source import MockDataSource
        return MockDataSource(config)

    raise ValueError(f"未知数据源类型: {config.DATA_SOURCE}")

