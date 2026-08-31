"""数据源层：统一封装行情/基本面数据的获取。

本框架把数据获取抽象为一个统一接口，方便在
同花顺(ths) / 备用数据源(akshare) / 模拟数据(mock) 之间切换。

外部统一使用 data_source.get_data_source(cfg) 获取实例。
"""

from .base import DataSourceBase, StockPool, StockData, get_data_source

__all__ = [
    "DataSourceBase",
    "StockPool",
    "StockData",
    "get_data_source",
]
