# 同花顺选股程序框架

一个可扩展的选股程序骨架，核心思路是：

> **数据源层（取数） → 策略层（你的规则） → 流水线编排 → 输出结果**

## 目录结构

```
THS_API/
├── main.py                      # 程序入口（全流程选股）
├── config.py                    # 全局配置中心（所有参数/集合）
├── pipeline.py                  # 选股流水线
├── requirements.txt             # 依赖清单
├── data_source/                 # 数据源层（多实现，可插拔）
│   ├── base.py                  #   抽象接口 + StockData + 工厂
│   ├── hithink_source.py        #   ⭐ 同花顺官方 REST 服务（主力）
│   ├── ths_source.py            #   同花顺本地编译库（占位）
│   ├── akshare_source.py        #   备用开源数据源（占位）
│   └── mock_source.py           #   模拟数据源（调试）
├── strategy/                    # 策略层（选股规则）
│   ├── base.py                  #   策略基类
│   ├── basic_filter.py          #   基础过滤（价格/流动性）
│   ├── momentum.py              #   动量策略（N日涨幅）
│   ├── fundamental.py           #   基本面策略（PE/ROE）
│   └── low_position.py          #   ⭐ 低位判断策略（历史百分位法）
├── scripts/                     # 业务脚本
│   ├── analyze_collection.py    #   集合快速分析（持仓/自选/观察）
│   ├── analyze_low_position.py  #   集合低位判断（历史百分位法）
│   └── query_star_market_pe.py  #   科创板 PE 排名
├── utils/output.py              # 结果保存 CSV
├── ths_api/                     # 放本地 THS 编译库（备用）
└── results/                     # 输出结果
```

## 快速开始

```bash
pip install -r requirements.txt

# 设置同花顺官方 API Key（hithink 数据源）
# 前往 https://fuyao.aicubes.cn/ 注册获取
$env:DATA_SOURCE="hithink"

# 跑全流程选股
python main.py

# 分析精选集合（持仓/自选/观察）
python scripts/analyze_collection.py all
```

## 低位判断策略（历史百分位法）

**回答的问题**：当前价格在过去的时间段里处于什么水平？

```
历史百分位 = (当前价 - 区间最低) / (区间最高 - 区间最低)
```
- 拉取股票过去若干年的**周K线**收盘价，找出最高/最低价；
- 计算当前价所处历史区间的百分位，**越接近 0 越低位**；
- 多周期综合：同时看长期(10年)/中期(3年)/短期(1年)，加权打分，避免单一周期误判。

### 参数说明（config.py 的 LOW_POSITION_RULE）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `periods` | 多周期(年) + 权重 + 标签 | 10年/3年/1年，权重 0.5/0.3/0.2 |
| `method` | 低位判定方式 | `percentile` |
| `percentile_threshold` | 百分位 < 此值视为低位（底部20%） | `0.20` |
| `ma_threshold` | 均线偏离 < 此值视为低位 | `-0.30` |
| `resample_rule` | 周K重采样规则 | `W` |

### method 可选值
- `percentile` ：纯历史百分位法（默认，最直观）
- `ma_deviation` ：均线偏离法（低于长期周均线 30% 以上）
- `any` ：任一方式命中即低位
- `both` ：两种方式都命中才算低位

### 运行
```bash
# 对持仓/自选/观察集合分别跑低位判断
python scripts/analyze_low_position.py all
python scripts/analyze_low_position.py holdings
```


## 量价背离策略（低位放量）

识别长周期周K线上低平台+放量的量价背离现象，视为低位筹码快速集中信号。

```
背离分数 = 价格跌幅 x 成交量增幅 x 100
成交量增幅 > 50% 时额外 x1.5
```

- 平台期：连续 10 周内价格波动 < 15% 视为一个平台期；
- 背离：新平台期均价 < 前一平台期，但平均成交量更高 -> 一次背离；
- 对最近 5 个平台期按越近权重越高加权平均，映射到 0-100；
- 得分 > 30 视为强背离信号。

### 参数说明（config.py 的 VOLUME_DIVERGENCE_RULE）

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| lookback_years | 回看年数 | 3 |
| platform_window | 平台期识别窗口（周） | 10 |
| price_change_threshold | 平台期内价格波动上限 | 0.15 |
| min_platform_periods | 最小平台期持续周数 | 8 |
| top_n_platforms | 参与对比的最近平台期数量 | 5 |
| strong_signal_threshold | 强背离信号阈值 | 30 |
| volume_increase_bonus | 放量额外加分的阈值 | 0.5 |

纯计算函数 compute_divergence_score(周KDataFrame, params) 输入含 date/close/volume 的周K数据，返回 {score, is_strong_divergence, details}。

## 精选股票集合（持仓/自选/观察）

在 `config.py` 底部维护三份列表：`HOLDINGS` / `WATCHLIST` / `OBSERVATION`。
每项 `{"code": "600519", "name": "贵州茅台"}`（代码 6 位即可）。

## 添加自己的选股规则

1. 在 `strategy/` 新建策略类，继承 `BaseStrategy` 并实现 `filter(stocks)`；
2. 把参数配置加入 `config.py`；
3. 在 `strategy/__init__.py` 导出；
4. 在 `pipeline.py` 的 `stages` 列表加入该策略（并开 `ENABLE_FILTERS`）。

## 说明

- 同花顺官方「hithink-finance」数据服务需要 API Key（https://fuyao.aicubes.cn/ 注册）。
- 低位判断、量价背离等策略均使用周K线数据，数据源会自动重采样。
- 历史日线数据已做本地缓存（cache/daily），之后只增量更新，减少请求量。
- 若需真实交易下单，可扩展 easytrader 等库。
