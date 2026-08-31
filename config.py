"""全局配置模块：集中管理所有可调参数。"""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()  # 加载 .env 文件（如有），避免敏感信息硬编码
except ImportError:
    pass  # dotenv 为可选依赖，缺失时仍可用环境变量/默认值


class Config:
    """程序运行的核心配置。"""

    # ---------- 数据源 ----------
    # 数据源类型：'ths' | 'akshare' | 'mock'
    #   ths   : 连接同花顺官方 API（需 ths_api/ths.py + THS.dll）
    #   akshare: 备用开源数据源（仅做测试/降级用）
    #   mock  : 本地模拟数据，方便纯逻辑开发调试
    DATA_SOURCE = os.getenv("DATA_SOURCE", "ths")

    # 同花顺连接超时（秒）
    THS_CONNECT_TIMEOUT = int(os.getenv("THS_CONNECT_TIMEOUT", "10"))
    # 同花顺返回数据超时（秒）
    THS_GET_DATA_TIMEOUT = int(os.getenv("THS_GET_DATA_TIMEOUT", "10"))

    # 历史日线缓存目录：拉到的股票历史数据存本地，之后只增量更新
    CACHE_DIR = os.getenv("CACHE_DIR", "cache/daily")

    # ---------- 选股范围 ----------
    # 支持的板块/市场：沪深A股
    MARKET_LIST = ["沪深A股", "上证A股", "深证A股"]

    # 排除的股票代码（如：退市、停牌、ST 等），可用通配符 *
    EXCLUDE_CODES = [
        "68*",   # 科创板（如需包含请删除）
        "30*",   # 创业板（如需包含请删除）
        # 更多排除规则可自行添加
    ]

    # ---------- 策略 / 规则 ----------
    # 流水线各步骤是否启用
    ENABLE_FILTERS = {
        "basic": True,      # 基础过滤（价格、流动性、ST 等）
        "momentum": True,   # 动量策略
        "fundamental": True,  # 基本面策略
        "low_position": True,  # 低位判断策略（历史百分位法）
        "volume_divergence": True,  # 量价背离策略（低位放量）
    }

    # 基础过滤规则
    BASIC_FILTER = {
        "min_price": float(os.getenv("MIN_PRICE", "5")),     # 最低股价
        "max_price": float(os.getenv("MAX_PRICE", "100")),   # 最高股价
        "min_amount": float(os.getenv("MIN_AMOUNT", "1e8")), # 最低成交额(元)
    }

    # 动量策略规则
    MOMENTUM_RULE = {
        "window": int(os.getenv("MOMENTUM_WINDOW", "20")),   # 回看N日
        "min_return": float(os.getenv("MOMENTUM_MIN_RETURN", "0.05")),  # 最低N日涨幅
    }

    # 基本面策略规则
    FUNDAMENTAL_RULE = {
        "min_pe": float(os.getenv("MIN_PE", "0")),        # 最低市盈率（>0）
        "max_pe": float(os.getenv("MAX_PE", "40")),       # 最高市盈率
        "min_roe": float(os.getenv("MIN_ROE", "0.1")),    # 最低净资产收益率
    }

    # ===========================================================
    # 低位判断策略（历史百分位法 + 多周期综合）
    # -----------------------------------------------------------
    # 回答："当前价格在过去的 N 段时间里处于什么水平？"
    # 逻辑：拉取每只股票过去若干年的周K线收盘价，
    #       计算当前价格所处历史区间（最高-最低）的百分位。
    # 多周期综合：同时看长期/中期/短期，加权打分，避免单一周期误判。
    # 所有参数均可自行修改。
    # -----------------------------------------------------------
    LOW_POSITION_RULE = {
        # 多周期(年)及其权重 — 长期看绝对底部、中期看下跌幅度、短期看企稳
        "periods": [
            {"years": 5,  "weight": 0.5, "label": "long"},
            {"years": 3,  "weight": 0.3, "label": "mid"},
            {"years": 1,  "weight": 0.2, "label": "short"},
        ],
        # 低位判定方式：
        #   "percentile"   : 纯历史百分位法
        #   "ma_deviation" : 均线偏离法
        #   "any"          : 任一方式命中即为低位
        #   "both"         : 两种方式都命中才算低位
        "method": "percentile",
        # 历史百分位低位阈值：百分位 < 该值 视为低位（默认底部20%）
        "percentile_threshold": 0.20,
        # 均线偏离低位阈值：(当前价-周均线)/周均线 < 该值 视为低位
        "ma_threshold": -0.30,
        # 周K重采样规则（'W-FRI' 以周五为一周）
        "resample_rule": "W",
    }

    # ===========================================================
    # 量价背离策略（低位放量 / 低位筹码集中）
    # -----------------------------------------------------------
    # 识别长周期周K线上"低平台 + 放量"的量价背离现象：
    #   新平台期均价低于前一平台期，但成交量明显放大。
    # 规则细节：
    #   背离分数 = 价格跌幅 × 成交量增幅 × 100
    #   成交量增幅 > VOLUME_INCREASE_BONUS 时额外 ×1.5
    #   对最近 TOP_N 个平台期按"越近权重越高"加权平均，
    #   映射到 0-100，超过 STRONG_SIGNAL_THRESHOLD 视为强背离。
    # -----------------------------------------------------------
    VOLUME_DIVERGENCE_RULE = {
        "lookback_years": 3,              # 回看年数（至少3年）
        "platform_window": 10,            # 平台期识别窗口（周）
        "price_change_threshold": 0.15,   # 平台期内价格波动上限（15%）
        "min_platform_periods": 8,        # 最小平台期持续周数
        "top_n_platforms": 5,             # 参与对比的最近平台期数量
        "strong_signal_threshold": 30,    # 强背离信号阈值
        "volume_increase_bonus": 0.5,     # 放量额外加分的阈值（50%）
        "resample_rule": "W",             # 周K重采样规则
    }

    # ---------- 输出 ----------
    OUTPUT_FILE = os.getenv("OUTPUT_FILE", "results/selected_stocks.csv")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # ===========================================================
    # 精选股票集合
    # -----------------------------------------------------------
    # 三个集合用于"快速分析"（无需全市场扫描）：
    #   持仓股 / 自选股 / 观察股
    # 每项是一个 dict：{"code": 股票代码, "name": 股票名称(可选)}
    # 代码用 6 位数字即可，程序会按交易所前缀自动补全 thscode。
    # 请填写你自己的股票。
    # ===========================================================

    # 1. 我的持仓股
    HOLDINGS = [
        {"code": "600519", "name": "贵州茅台"},
        {"code": "300750", "name": "宁德时代"},
        {"code": "002241", "name": "歌尔股份"},
    ]

    # 2. 我的自选股
    WATCHLIST = [
        {"code": "000001", "name": "平安银行"},
        {"code": "600036", "name": "招商银行"},
    ]

    # 3. 我的观察股
    OBSERVATION = [
        {"code": "601318", "name": "中国平安"},
        {"code": "002415", "name": "海康威视"},
    ]

    # 给集合起的名字（供命令行与展示用）
    COLLECTIONS = {
        "holdings": "持仓股",
        "watchlist": "自选股",
        "observation": "观察股",
    }

