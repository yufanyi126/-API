"""策略基类：所有选股策略都继承它。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from data_source.base import StockData


class BaseStrategy(ABC):
    """策略抽象接口。"""

    def __init__(self, config, data_source):
        self._cfg = config
        self._ds = data_source

    @abstractmethod
    def filter(self, stocks: List[StockData]) -> List[StockData]:
        """对候选股票列表执行规则，返回过滤/打分后的子集。

        实现方应返回新列表（不修改入参），并记录筛选原因以便日志输出。
        """

    def name(self) -> str:
        """策略名称，用于日志与结果标记。"""
        return self.__class__.__name__
