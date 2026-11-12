"""量价背离策略（低位放量 / 低位筹码集中）。

核心逻辑：识别长周期周K线上的"低平台 + 放量"量价背离现象——
新平台期的平均股价低于前一个平台期，但平均成交量更高。
这通常被视为"低位筹码快速集中"的信号，放量越大、价格越低，信号越强。

规则要点：
  - 使用周K线，回看至少 3 年；
  - 平台期：连续 platform_window 周内价格波动 < price_change_threshold；
  - 背离：相邻平台期，均价更低且均量更高；
  - 背离分数 = 价格跌幅 × 成交量增幅 × 100；
      成交量增幅 > volume_increase_bonus 时额外 ×1.5；
  - 取最近 top_n_platforms 个平台期，按"越近权重越高"加权平均，映射 0-100；
  - 得分 > strong_signal_threshold 视为强背离。

所有参数通过 config.VOLUME_DIVERGENCE_RULE 统一管理。
"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from data_source.base import StockData
from .base import BaseStrategy


# ----------------------------------------------------------------------
# 纯计算函数：输入周K DataFrame，返回结果字典
# ----------------------------------------------------------------------
def compute_divergence_score(
    weekly: pd.DataFrame,
    params: dict,
) -> Dict:
    """计算量价背离综合得分。

    参数
    ----
    weekly : pandas.DataFrame
        周K线数据，需含 close 与 volume 列，date 可为索引或列，按时间升序。
    params : dict
        参数，见 config.VOLUME_DIVERGENCE_RULE。

    返回
    ----
    dict : {'score', 'is_strong_divergence', 'details': {...}}
    """
    window = int(params.get("platform_window", 10))
    threshold = float(params.get("price_change_threshold", 0.15))
    min_periods = int(params.get("min_platform_periods", 8))
    top_n = int(params.get("top_n_platforms", 5))
    strong_th = float(params.get("strong_signal_threshold", 30))
    vol_bonus = float(params.get("volume_increase_bonus", 0.5))

    # ---- 标准化 DataFrame ----
    df = weekly.copy()
    if "date" not in df.columns:
        df = df.reset_index()  # 把日期索引转回列
    df = df.sort_values("date").reset_index(drop=True)
    if "close" not in df.columns or "volume" not in df.columns:
        raise ValueError("输入需包含 close 和 volume 列")

    closes = df["close"].astype(float).tolist()
    volumes = df["volume"].astype(float).tolist()

    result = {
        "score": 0.0,
        "is_strong_divergence": False,
        "details": {
            "total_platforms": 0,
            "compared_platforms": 0,
            "divergence_count": 0,
            "latest_divergence_score": 0.0,
        },
    }

    # ---- 识别平台期 ----
    platforms = _identify_platforms(closes, window, threshold, min_periods)
    if len(platforms) < 2:
        return result
    result["details"]["total_platforms"] = len(platforms)

    # ---- 每个平台期的均价 / 均量 ----
    seg_metrics = []  # (avg_price, avg_volume)
    for (a, b) in platforms:
        seg_metrics.append((sum(closes[a:b + 1]) / (b - a + 1),
                            sum(volumes[a:b + 1]) / (b - a + 1)))

    # ---- 按平台期顺序计算背离分数 ----
    # 平台期按时间从旧到新排列（seg_metrics 索引 0 最旧）
    scores = []  # 每个平台期相对上一个的背离分数（非背离为0）
    latest_div_score = 0.0
    divergence_count = 0
    for k in range(1, len(seg_metrics)):
        prev_price, prev_vol = seg_metrics[k - 1]
        new_price, new_vol = seg_metrics[k]

        # 背离条件：均价更低 且 均量更高
        if new_price < prev_price and new_vol > prev_vol:
            price_drop = (prev_price - new_price) / prev_price
            vol_rise = (new_vol - prev_vol) / prev_vol
            dscore = price_drop * vol_rise * 100.0
            if vol_rise > vol_bonus:
                dscore *= 1.5
            scores.append(dscore)
            divergence_count += 1
            latest_div_score = dscore
        else:
            scores.append(0.0)

    result["details"]["divergence_count"] = divergence_count
    result["details"]["latest_divergence_score"] = round(latest_div_score, 2)

    # ---- 取最近 top_n 个平台期的背离分数做加权平均 ----
    # 最近 top_n 个对应 seg_metrics 的最后 top_n 个，背离分数在 scores 中
    compared = min(top_n, len(scores))  # 最近 compared+1 个平台期产生 compared 个分数
    if compared == 0:
        result["details"]["compared_platforms"] = 0
        return result
    # scores 的最后 compared 个
    tail = scores[-compared:]
    # 时间越近权重越高：位置 0 最旧、不权重低
    weights = [i + 1 for i in range(len(tail))]
    total_w = sum(weights)
    weighted = sum(s * w for s, w in zip(tail, weights)) / total_w

    result["details"]["compared_platforms"] = compared
    # 映射到 0-100（截断）
    result["score"] = round(min(100.0, weighted), 2)
    result["is_strong_divergence"] = result["score"] > strong_th
    return result


def _identify_platforms(
    closes: List[float], window: int, threshold: float, min_periods: int
) -> List[tuple]:
    """识别平台期：返回 [(start_idx, end_idx)]，闭区间，按时间升序。"""
    platforms: List[tuple] = []
    n = len(closes)
    i = 0
    while i < n:
        j = i
        while j < n:
            seg = closes[i:j + 1]
            if len(seg) >= window and (max(seg) - min(seg)) / min(seg) > threshold:
                break
            j += 1
        end = j - 1
        if end - i + 1 >= max(window, min_periods):
            platforms.append((i, end))
        i = end + 1
    return platforms


# ----------------------------------------------------------------------
# 选股策略类：接入 pipeline
# ----------------------------------------------------------------------
class VolumeDivergenceStrategy(BaseStrategy):
    """基于长周期周K线量价背离的低位选股策略。"""

    def __init__(self, config, data_source):
        super().__init__(config, data_source)
        self._rule = getattr(config, "VOLUME_DIVERGENCE_RULE", {})

    def _evaluate(self, stock: StockData) -> Dict:
        lookback = int(self._rule.get("lookback_years", 3))
        # 用日线缓存取数据
        df = self._ds.get_daily_bars(stock.code, years=lookback)
        if df is None or df.empty:
            return {"score": 0.0, "is_strong_divergence": False,
                    "details": {"total_platforms": 0, "compared_platforms": 0,
                                "divergence_count": 0, "latest_divergence_score": 0.0}}
        data_freq = self._rule.get("data_freq", "D")
        resample = self._rule.get("resample_rule", "D")
        if data_freq.upper() == "W":
            # 周线：按周重采样（收盘取末值，量取和）
            to_eval = (df.set_index("date")
                       .resample(resample)
                       .agg({"close": "last", "volume": "sum"})
                       .dropna())
            to_eval = to_eval.reset_index()
        else:
            # 日线：直接用日线 OHLCV
            to_eval = df[["date", "close", "volume"]].copy()
        return compute_divergence_score(to_eval, self._rule)

    def filter(self, stocks: List[StockData]) -> List[StockData]:
        kept: List[StockData] = []
        for s in stocks:
            r = self._evaluate(s)
            if r["is_strong_divergence"]:
                kept.append(s)
                print(f"  [量价背离] 命中 {s.code} {s.name} 得分={r['score']}"
                      f" 背离次数={r['details']['divergence_count']}"
                      f" 平台数={r['details']['total_platforms']}")
            else:
                print(f"  [量价背离] 过滤 {s.code} {s.name} 得分={r['score']}")
        print(f"策略 {self.name()}: 过滤后 {len(stocks)} -> {len(kept)} 只")
        return kept
