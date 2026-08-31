"""低位判断策略（历史百分位法 + 多周期综合）。

回答的问题：当前价格，在过去的一段时间里，处于什么水平？

核心逻辑：
  1. 拉取每只股票过去若干年（默认最大周期）的前复权日线；
  2. 重采样成周K线，取每周收盘价；
  3. 对每个时间周期（长期/中期/短期）计算历史百分位：
         percentile = (当前价 - 区间最低) / (区间最高 - 区间最低)
     区间最高/最低取自该周期内的周K线收盘价序列；
  4. 按各周期权重加权得到"综合位置分"，分值 ∈ [0,1]，越接近 0 越低；
  5. 支持第二种口径"均线偏离法"：
         (当前价 - 周期周均线) / 周期周均线
  6. 按配置的低位判定方式与阈值，判断是否处于低位。

所有周期、权重、阈值均可通过 config.LOW_POSITION_RULE 修改。
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from data_source.base import StockData
from .base import BaseStrategy


class LowPositionStrategy(BaseStrategy):
    """基于历史百分位与多周期综合的低位判断策略。"""

    def __init__(self, config, data_source):
        super().__init__(config, data_source)
        self._rule = getattr(config, "LOW_POSITION_RULE", {})

    def _max_years(self) -> int:
        periods = self._rule.get("periods", [])
        if not periods:
            return 3
        return max(p.get("years", 1) for p in periods)

    def _single_percentile(self, current: float, weekly: pd.Series) -> float:
        """单个周期的历史百分位：(当前价-min)/(max-min)。"""
        if weekly is None or len(weekly) < 2:
            return None
        wk = weekly.dropna()
        if len(wk) < 2:
            return None
        lo = wk.min()
        hi = wk.max()
        if hi == lo:
            return 0.0
        return float((current - lo) / (hi - lo))

    def _single_ma_dev(self, current: float, weekly: pd.Series) -> float:
        """单个周期的均线偏离：(当前价-周期周均线)/周期周均线。"""
        if weekly is None or len(weekly) < 1:
            return None
        wk = weekly.dropna()
        if len(wk) < 1:
            return None
        mean = wk.mean()
        if mean == 0:
            return None
        return float((current - mean) / mean)

    def _evaluate(self, stock: StockData) -> dict:
        """对单只股票计算多周期位置评分，返回诊断信息与是否低位。"""
        code = stock.code
        result = {
            "code": code,
            "name": stock.name,
            "price": stock.price,
            "low": False,
            "score": None,
            "pct_details": [],
            "reason": "",
        }

        max_years = self._max_years()
        df = self._ds.get_daily_bars(code, years=max_years)
        if df is None or df.empty:
            result["reason"] = "无足够历史数据"
            return result

        current = stock.price
        resample_rule = self._rule.get("resample_rule", "W")

        # 重采样成周K（每周最后一个交易日收盘价）
        df = df.set_index("date")
        weekly = df["close"].resample(resample_rule).last().dropna()
        total_weeks = len(weekly)

        # 对每个周期取最近 years 年的周K子序列计算
        pct_scores = []      # 各周期历史百分位
        ma_scores = []       # 各周期均线偏离
        weights = []         # 各周期权重
        for p in self._rule.get("periods", []):
            years = p.get("years", 1)
            w = p.get("weight", 1.0)
            label = p.get("label", years)
            # 取最近 years 年内（按末个交易日往前）的周K
            if total_weeks <= 1:
                sub = weekly
            else:
                cutoff_date = df.index[-1] - pd.DateOffset(years=years)
                sub = weekly[weekly.index >= cutoff_date]
            pct = self._single_percentile(current, sub)
            mad = self._single_ma_dev(current, sub)
            pct_scores.append(pct)
            ma_scores.append(mad)
            weights.append(w)
            result["pct_details"].append({
                "label": label, "years": years,
                "pct": pct, "ma_dev": mad, "weeks": len(sub),
            })

        # 加权综合（忽略空值周期，若全空则无法判定）
        valid = [(p, w) for p, w in zip(pct_scores, weights) if p is not None]
        if not valid:
            result["reason"] = "多周期均无数据"
            return result
        total_w = sum(w for _, w in valid)
        pct_combined = sum(p * w for p, w in valid) / total_w

        valid_ma = [(m, w) for m, w in zip(ma_scores, weights) if m is not None]
        ma_combined = None
        if valid_ma:
            tw = sum(w for _, w in valid_ma)
            ma_combined = sum(m * w for m, w in valid_ma) / tw
        result["score"] = pct_combined

        # 低位判定（按 method）
        method = self._rule.get("method", "percentile")
        pct_th = self._rule.get("percentile_threshold", 0.20)
        ma_th = self._rule.get("ma_threshold", -0.30)

        pct_low = pct_combined < pct_th
        ma_low = (ma_combined is not None) and (ma_combined < ma_th)

        if method == "percentile":
            low = pct_low
        elif method == "ma_deviation":
            low = ma_low
        elif method == "any":
            low = pct_low or ma_low
        else:  # both（默认）
            low = pct_low and ma_low

        result["low"] = low
        detail_str = ", ".join(
            f"{d['label']}: 百分位={d['pct']:.3f} 均线偏离={d['ma_dev'] if d['ma_dev'] is not None else float('nan'):.3f}" if d['pct'] is not None
            else f"{d['label']}: 无数据"
            for d in result["pct_details"]
        )
        result["reason"] = (
            f"综合百分位={pct_combined:.3f}, "
            f"综合均线偏离={ma_combined if ma_combined is not None else float('nan'):.3f}, "
            f"detail[{detail_str}]"
        )
        return result

    def filter(self, stocks: List[StockData]) -> List[StockData]:
        kept: List[StockData] = []
        for s in stocks:
            r = self._evaluate(s)
            if r["low"]:
                kept.append(s)
                print(f"  [LowPosition] 命中低位 {s.code} {s.name} "
                      f"综合百分位={r['score']:.3f}\t{r['reason']}")
            else:
                print(f"  [LowPosition] 过滤 {s.code} {s.name} "
                      f"综合百分位={r['score'] if r['score'] is not None else '-'}")
        print(f"策略 {self.name()}: 过滤后 {len(stocks)} -> {len(kept)} 只")
        return kept
