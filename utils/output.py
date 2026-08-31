"""结果输出工具：将选股结果保存为 CSV。"""
from __future__ import annotations

import os
from typing import List

import pandas as pd

from data_source.base import StockData


def to_dataframe(stocks: List[StockData]) -> pd.DataFrame:
    """把 StockData 列表转为 DataFrame。"""
    rows = []
    for sd in stocks:
        rows.append({
            "code": sd.code,
            "name": sd.name,
            "price": sd.price,
            "change_pct": sd.change_pct,
            "amount": sd.amount,
            "pe": sd.pe,
            "roe": sd.roe,
            "history": sd.history.tolist() if sd.history is not None else None,
        })
    return pd.DataFrame(rows)


def save_results(stocks: List[StockData], filepath: str) -> str:
    """保存结果为 CSV，返回保存路径。"""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    df = to_dataframe(stocks)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath
