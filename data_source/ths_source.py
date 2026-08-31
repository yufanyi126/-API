"""同花顺官方 API 数据源实现。

需要准备：
1. 从同花顺官方（或 iFinD 权限）获取 ths_api/THS.py 与 ths_api/THS.dll；
2. 通过 pip 安装 ths 相关依赖（如有）；
3. 本地安装并登录同花顺客户端（用于数据读取）。

同花顺官方库的典型用法（THS 类）：
    import THS
    THS.start('userpath', 'mypassword')          # 登录
    THS.DataType = THS.THSDataType.HistoryPeriod  # 历史数据
    code, types = THS.HQ_GetData(label, ...)      # 取数
    THS.stop()                                    # 退出

由于 THS 库为官方私有编译库，接口细节各版本略有差异，这里把调用点
封装为独立方法，便于你对照自己的 THS.py 实际接口做适配。
"""
from __future__ import annotations

import os
import sys
from typing import List, Optional

import pandas as pd

from .base import DataSourceBase, StockData

# 把同花顺官方库目录 ths_api/ 加入模块搜索路径，便于 import THS
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_THS_API_DIR = os.path.join(_ROOT, "ths_api")
if _THS_API_DIR not in sys.path:
    sys.path.insert(0, _THS_API_DIR)


class THSDataSource(DataSourceBase):
    """基于同花顺官方 THS 库的数据源。"""

    def __init__(self, config):
        super().__init__(config)
        self._ths = None  # THS 模块对象，懒加载
        self._connected = False
        # 同花顺登录凭据（建议通过 .env 注入，避免硬编码）
        self._user_path = getattr(config, "THS_USER_PATH", None)
        self._password = getattr(config, "THS_PASSWORD", None)

    # ---------------- 连接 ----------------
    def connect(self) -> bool:
        try:
            import THS  # 从 ths_api 目录导入官方库

            self._ths = THS
            # 登录同花顺客户端
            ok = THS.start(self._user_path or "", self._password or "")
            if not ok:
                raise RuntimeError("同花顺登录失败，请确认客户端已打开并授权")
            self._connected = True
            return True
        except ImportError as exc:
            raise RuntimeError(
                "未找到同花顺官方库 THS.py/THS.dll，"
                "请将其放到 ths_api/ 目录，或在 DATA_SOURCE 中改用 akshare/mock"
            ) from exc

    # ---------------- 股票池 ----------------
    def get_stock_pool(self, market: str = "沪深A股") -> List[str]:
        if not self._connected:
            self.connect()

        # 同花顺示例：通过板块成分获取股票代码
        # 具体写法取决于你的 THS 版本，下面是示意
        # label = {
        #     "沪深A股": "上证A股+深证A股",
        #     "上证A股": "上证A股",
        #     "深证A股": "深证A股",
        # }.get(market, "沪深A股")
        #
        # code, _types = self._ths.HQ_GetData(label=label, ...)
        # codes = [str(c[0]) for c in code]

        # ---- 占位返回，请按实际接口替换 ----
        raise NotImplementedError(
            "THSDataSource.get_stock_pool 需要根据你的 THS.py 实际接口实现"
        )

    # ---------------- 实时快照 ----------------
    def get_stock_quote(self, code: str) -> Optional[StockData]:
        if not self._connected:
            self.connect()

        # 同花顺实时行情接口示意（具体字段随版本而异）
        # code_, _ = self._ths.HQ_GetData(label=code, ...)
        # 从返回里取 名称/现价/涨跌幅/成交额
        raise NotImplementedError(
            "THSDataSource.get_stock_quote 需要根据你的 THS.py 实际接口实现"
        )

    # ---------------- 历史数据 ----------------
    def get_history(self, code: str, days: int = 60) -> Optional[pd.Series]:
        if not self._connected:
            self.connect()

        # 同花顺历史行情接口示意：
        # self._ths.DataType = self._ths.THSDataType.HistoryPeriod
        # code_, types = self._ths.HQ_GetData(period='日线', begin_time=..., end_time=..., ...)
        # 取 'close' 字段组成 pd.Series，索引为日期

        raise NotImplementedError(
            "THSDataSource.get_history 需要根据你的 THS.py 实际接口实现"
        )

    # ---------------- 基本面 ----------------
    def get_fundamentals(self, code: str) -> StockData:
        if not self._connected:
            self.connect()

        # 同花顺财务数据接口示意：获取 PE、ROE 等指标
        raise NotImplementedError(
            "THSDataSource.get_fundamentals 需要根据你的 THS.py 实际接口实现"
        )

    def close(self) -> None:
        if self._connected and self._ths is not None:
            try:
                self._ths.stop()
            except Exception:
                pass
            self._connected = False
