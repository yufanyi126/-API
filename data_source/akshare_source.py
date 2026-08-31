"""备用开源数据源：基于 akshare 获取行情与基本面。

作为同花顺 API 不可用时的降级/测试方案，接口与 ths_source 保持一致，
方便在 config 中一行切换。
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd

from .base import DataSourceBase, StockData


class AKShareDataSource(DataSourceBase):
    """基于 akshare 的数据源。""

    def connect(self) -> bool:
        try:
            import akshare as ak  # noqa: F401
            return True
        except ImportError as exc:
            raise RuntimeError("请先安装 akshare: pip install akshare") from exc

    def get_stock_pool(self, market: str = "沪深A股") -> List[str]:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        return df["code"].astype(str).tolist()

    def get_stock_quote(self, code: str) -> Optional[StockData]:
        import akshare as ak
        try:
            df = ak.stock_individual_info_em(symbol=code)
        except Exception:
            return None
        price_map = df.set_index("item")["value"].to_dict()
        return StockData(
            code=code,
            name=str(price_map.get("股票简称", "")),
            price=float(price_map.get("当前价格") or 0.0),
        )

    def get_history(self, code: str, days: int = 60) -> Optional[pd.Series]:
        import akshare as ak
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                    start_date="19900101", adjust="qfq")
        except Exception:
            return None
        df = df.tail(days)
        s = pd.Series(df["收盘"].values, index=pd.to_datetime(df["日期"]), name="close")
        return s

    def get_fundamentals(self, code: str) -> StockData:
        sd = self.get_stock_quote(code)
        if sd is None:
            return StockData(code=code)
        # akshare 的财务指标接口较多，这里留占位，可按需补全
        sd.pe = None
        sd.roe = None
        return sd
