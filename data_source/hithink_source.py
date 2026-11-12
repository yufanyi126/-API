"""同花顺官方金融数据服务（hithink-finance）数据源实现。

基于同花顺官方 REST API（https://fuyao.aicubes.cn），无需 Node.js。
使用前需要：
  1. 前往 https://fuyao.aicubes.cn/ 注册并获取统一 API Key；
  2. 将 Key 配置为环境变量 HITHINK_FINANCE_API_KEY
     （或写入用户级 credentials.env）。

通用协议：
  - Base URL : https://fuyao.aicubes.cn
  - 方法     : GET
  - 认证     : HTTP Header  X-api-key: <key>
  - 成功判断 : HTTP 200 且响应 { code: 0 }
  - 响应信封 : { code, message, request_id, data }
本数据源的取数方法均走远端 REST，适合实时/最新数据的查询。
"""
from __future__ import annotations

import os
import time
from typing import List, Optional

import pandas as pd
import requests

from .base import DataSourceBase, StockData

_BASE_URL = "https://fuyao.aicubes.cn"


class HithinkDataSource(DataSourceBase):
    """通过同花顺官方 REST API 获取 A 股数据的数据源。"""

    def __init__(self, config):
        super().__init__(config)
        # 从环境变量或用户级凭据文件读取 API Key
        self._api_key = self._load_api_key()
        self._session = requests.Session()

    def _load_api_key(self) -> str:
        key = os.getenv("HITHINK_FINANCE_API_KEY", "")
        if key:
            return key
        # 兜底：读取用户级 credentials.env
        try:
            cred_path = os.path.join(
                os.environ.get("APPDATA", ""), "hithink-finance", "credentials.env"
            )
            with open(cred_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("HITHINK_FINANCE_API_KEY="):
                        return line.split("=", 1)[1].strip()
        except (OSError, ValueError):
            pass
        return ""

    # ---------------- 底层请求 ----------------
    def _get(self, path: str, params: dict, retries: int = 3) -> dict:
        """发起 GET 请求并解析官方响应信封，返回 data 字段。

        对网络错误/代理抖动/限流(4001)/服务端错误(5xxx)做指数退避重试。
        """
        if not self._api_key:
            raise RuntimeError(
                "缺少同花顺 API Key。请前往 https://fuyao.aicubes.cn/ 注册后，"
                "设置环境变量 HITHINK_FINANCE_API_KEY。"
            )
        last_err = None
        for attempt in range(retries):
            try:
                resp = self._session.get(
                    f"{_BASE_URL}{path}",
                    params=params,
                    headers={"X-api-key": self._api_key},
                    timeout=getattr(self._cfg, "THS_CONNECT_TIMEOUT", 10),
                )
                resp.raise_for_status()
                payload = resp.json()
                code = payload.get("code")
                # 限流（4001）或服务端异常（5xxx、网络类）重试
                if code in (4001,) or (isinstance(code, int) and 5001 <= code <= 5999):
                    raise _RetryableError(f"code={code}")
                if code != 0:
                    raise RuntimeError(
                        f"同花顺接口错误 code={code}: {payload.get('message')}"
                    )
                return payload.get("data")
            except (_RetryableError, requests.exceptions.RequestException) as exc:
                last_err = exc
                if attempt < retries - 1:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
            except RuntimeError:
                raise  # 业务/参数错误不重试
        raise RuntimeError(f"同花顺请求失败（已重试 {retries} 次）: {last_err}")

    # ---------------- 连接（无状态，校验 Key） ----------------
    def connect(self) -> bool:
        # 用一个最小请求验证 Key 可用性
        try:
            self._get("/api/meta/tickers/search", {"q": "600519", "limit": 1})
            return True
        except Exception as exc:
            raise RuntimeError(f"同花顺数据服务连接失败: {exc}") from exc

    # ---------------- 股票池 ----------------
    def get_stock_pool(self, market: str = "沪深A股") -> List[str]:
        """获取全市场 A 股代码列表。"""
        return self.get_full_tickers()

    def get_full_tickers(self, asset_type: str = "a-share",
                         exchanges: str = "SH,SZ,BJ") -> List[str]:
        """分页拉取全市场指定资产类别代码表（每页最大 10000）。"""
        codes: List[str] = []
        limit = 10000
        offset = 0
        while True:
            data = self._get("/api/meta/tickers/list", {
                "exchange": exchanges,
                "asset_type": asset_type,
                "limit": limit,
                "offset": offset,
            })
            items = (data or {}).get("item") or []
            codes.extend(item["ticker"] for item in items)
            if len(items) < limit:
                break
            offset += limit
        return codes

    def get_valuation_batch(self, codes: List[str]) -> List[StockData]:
        """批量查询估值快照，填充每只股票的 PE（pe_ttm）。
        实现：GET /api/a-share/valuations/snapshot（每次最多 100 个 thscode）
        """
        results: List[StockData] = []
        batch_size = 100
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            thscodes = ",".join(_full_thscode(c) for c in batch)
            data = self._get("/api/a-share/valuations/snapshot", {"thscodes": thscodes})
            for item in (data or {}).get("item") or []:
                results.append(StockData(
                    code=item["ticker"],
                    name=item.get("name", ""),
                    pe=item.get("pe_ttm"),
                ))
        return results

    def get_stock_pool_by_index(self, thscode: str) -> List[StockData]:
        """获取某个同花顺指数/板块的成分股列表（thscode，如 000688.SH 等）。
        调用：GET /api/a-share-index/constituents/ths-stock-list?thscode=...
        """
        data = self._get(
            "/api/a-share-index/constituents/ths-stock-list", {"thscode": thscode}
        )
        stocks: List[StockData] = []
        for item in data.get("item", []):
            stocks.append(StockData(code=item["ticker"], name=item.get("name", "")))
        return stocks

    # ---------------- 实时快照 ----------------
    def get_stock_quote(self, code: str) -> Optional[StockData]:
        """获取单只股票实时快照。

        行情快照端点不返回股票的 name，这里只填行情字段；
        name 可在批量方法中通过估值/元数据接口补充。
        """
        thscode = _full_thscode(code)
        data = self._get("/api/a-share/prices/snapshot", {"thscodes": thscode})
        items = (data or {}).get("item") or []
        if not items:
            return None
        it = items[0]
        return StockData(
            code=code,
            price=float(it.get("last_price") or 0.0),
            change_pct=float(it.get("price_change_ratio_pct") or 0.0),
            amount=float(it.get("turnover") or 0.0),
        )

    def get_quotes_batch(self, codes: List[str]) -> List[StockData]:
        """批量获取实时快照 + 名称 + PE。

        结合两块官方批量接口：
          - 行情:  GET /api/a-share/prices/snapshot?thscodes=...
          - 估值:  GET /api/a-share/valuations/snapshot?thscodes=...
        估值接口返回 name，行情接口返回价格/涨跌幅/成交额。
        回归条数与请求一致，方便后续按 code 合并。
        """
        result: List[StockData] = []
        batch_size = 100
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            thscodes = ",".join(_full_thscode(c) for c in batch)

            # 行情
            price_data = self._get(
                "/api/a-share/prices/snapshot", {"thscodes": thscodes}
            )
            price_map = {}
            for it in (price_data or {}).get("item") or []:
                price_map[it["ticker"]] = it

            # 估值（提供 name 与 pe）
            val_data = self._get(
                "/api/a-share/valuations/snapshot", {"thscodes": thscodes}
            )
            val_map = {}
            for it in (val_data or {}).get("item") or []:
                val_map[it["ticker"]] = it

            for code in batch:
                p = price_map.get(code, {})
                v = val_map.get(code, {})
                result.append(StockData(
                    code=code,
                    name=v.get("name", "") or p.get("name", ""),
                    price=float(p.get("last_price") or 0.0),
                    change_pct=float(p.get("price_change_ratio_pct") or 0.0),
                    amount=float(p.get("turnover") or 0.0),
                    pe=v.get("pe_ttm"),
                ))
        return result

    # ---------------- 历史数据 ----------------
    def get_history(self, code: str, days: int = 60) -> Optional[pd.Series]:
        thscode = _full_thscode(code)
        end = int(time.time() * 1000)
        start = end - days * 24 * 3600 * 1000
        data = self._get(
            "/api/a-share/prices/historical",
            {"thscode": thscode, "interval": "1d",
             "start": start, "end": end, "adjust": "forward"},
        )
        items = (data or {}).get("item") or []
        if not items:
            return None
        s = pd.Series(
            [float(i["close_price"]) for i in items],
            index=pd.to_datetime([i["date_ms"] for i in items], unit="ms"),
            name="close",
        )
        return s.sort_index().tail(days)

    # ---------------- 通用多周期K线(日/周/60分钟等) ----------------
    def _fetch_ohlcv(self, code: str, interval: str = "1d",
                     start_ms: int = None, end_ms: int = None,
                     limit: int = None) -> Optional[pd.DataFrame]:
        """按 interval 拉历史 OHLCV。interval 形如 '1d'/'1w'/'60m'/'15m'。

        返回 DataFrame 列为 [date, open, high, low, close, volume, turnover]。
        """
        thscode = _full_thscode(code)
        end_ms = end_ms or int(time.time() * 1000)
        params = {
            "thscode": thscode,
            "interval": interval,
            "adjust": "forward",
            "end": end_ms,
        }
        if start_ms is not None:
            params["start"] = start_ms
        data = self._get("/api/a-share/prices/historical", params)
        items = (data or {}).get("item") or []
        if not items:
            return None
        df = pd.DataFrame(items)
        df["date"] = pd.to_datetime(df["date_ms"], unit="ms")
        rename = {
            "open_price": "open", "high_price": "high", "low_price": "low",
            "close_price": "close", "volume": "volume", "turnover": "turnover",
            "date_ms": "date_ms",
        }
        df = df.rename(columns=rename)
        keep = [c for c in ["date", "open", "high", "low", "close",
                            "volume", "turnover"] if c in df.columns]
        for col in keep[1:]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[keep].dropna()
        df = df.sort_values("date").reset_index(drop=True)
        if limit is not None:
            df = df.tail(limit).reset_index(drop=True)
        return df

    def get_kline(self, code: str, interval: str = "1d",
                  limit: int = None, days: int = None) -> Optional[pd.DataFrame]:
        """公开入口：取某周期最近 N 根K线。

        limit: 返回最近多少根；days: 回溯多少天（用于周K/月K等较长跨度）。
        至少给其中之一；两者都给时限数取 limit。
        """
        end_ms = int(time.time() * 1000)
        start_ms = None
        if days:
            start_ms = end_ms - days * 24 * 3600 * 1000
        return self._fetch_ohlcv(code, interval=interval,
                                 start_ms=start_ms, end_ms=end_ms, limit=limit)

    def get_daily_bars(self, code: str, years: int = 3) -> Optional[pd.DataFrame]:
        """获取某只股票近 N 年的前复权日线 OHLCV 数据（带本地缓存 + 增量更新）。

        首次调用会把数据缓存到 CACHE_DIR/<code>.csv；
        之后的调用只拉取缓存结束日之后的新数据，合并后写回，减少请求量。

        返回 DataFrame，列为 [date, open, high, low, close, volume, turnover]，
        date 为 datetime，按时间升序。
        """
        thscode = _full_thscode(code)
        cache_dir = self._cfg.CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{code}.csv")

        # 1. 读取已有缓存
        cached = None
        if os.path.exists(cache_path):
            try:
                cached = pd.read_csv(cache_path)
                cached["date"] = pd.to_datetime(cached["date"])
            except Exception:
                cached = None

        # 2. 需要的起始日期（N 年前）
        now = pd.Timestamp.now()
        need_start = now - pd.DateOffset(years=years)

        # 3. 增量请求的区间
        fetch_start = need_start
        if cached is not None and not cached.empty:
            last_date = cached["date"].max()
            if last_date >= now - pd.Timedelta(days=1):
                # 缓存已是最新，无需请求
                return cached.sort_values("date").reset_index(drop=True)
            # 断点续传：从缓存末日后一天开始
            fetch_start = last_date + pd.Timedelta(days=1)

        end_ms = int(now.timestamp() * 1000)
        start_ms = int(fetch_start.timestamp() * 1000)

        data = self._get(
            "/api/a-share/prices/historical",
            {"thscode": thscode, "interval": "1d",
             "start": start_ms, "end": end_ms, "adjust": "forward"},
        )
        items = (data or {}).get("item") or []
        if not items and cached is None:
            return None

        new_df = None
        if items:
            new_df = pd.DataFrame(items)
            new_df["date"] = pd.to_datetime(new_df["date_ms"], unit="ms")
            rename = {
                "open_price": "open", "high_price": "high", "low_price": "low",
                "close_price": "close", "volume": "volume", "turnover": "turnover",
            }
            new_df = new_df.rename(columns=rename)
            for col in ["open", "high", "low", "close", "volume", "turnover"]:
                if col in new_df.columns:
                    new_df[col] = pd.to_numeric(new_df[col], errors="coerce")
            new_df = new_df[["date", "open", "high", "low", "close", "volume", "turnover"]]
            new_df = new_df.dropna()

        # 4. 合并缓存 + 新增，去重
        frames = [f for f in [cached, new_df] if f is not None and not f.empty]
        if not frames:
            return None
        merged = pd.concat(frames, ignore_index=True)
        merged = merged.drop_duplicates(subset="date", keep="last")
        merged = merged.sort_values("date").reset_index(drop=True)

        # 5. 写回缓存
        merged.to_csv(cache_path, index=False, encoding="utf-8")
        return merged

    # ---------------- 成交量数据（复用日线缓存） ----------------
    def get_daily_volume(self, code: str, years: int = 3) -> Optional[pd.DataFrame]:
        """获取某只股票近 N 年的日成交量/成交额，并单独落地缓存。

        数据来自 get_daily_bars（与股价同一份日线缓存，不重复请求）；
        同时额外写到 <CACHE_DIR>/<code>_volume.csv，便于后续成交量分析
        直接读取，无需再拉历史。
        """
        df = super().get_daily_volume(code, years=years)
        if df is None or df.empty:
            return None
        cache_dir = self._cfg.CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)
        vol_path = os.path.join(cache_dir, f"{code}_volume.csv")
        df.to_csv(vol_path, index=False, encoding="utf-8")
        return df

    # ---------------- 基本面 / 估值 ----------------
    def get_fundamentals(self, code: str) -> StockData:
        """查询最新估值快照，填充 PE 等指标。

        注意：官方估值端点固定返回 PE/PB/PS/PCF 五项，不含 ROE。
        ROE 需通过财务指标端点另行获取，这里留作可扩展点。
        """
        thscode = _full_thscode(code)
        data = self._get("/api/a-share/valuations/snapshot", {"thscodes": thscode})
        items = (data or {}).get("item") or []
        sd = self.get_stock_quote(code) or StockData(code=code)
        if items:
            it = items[0]
            sd.pe = it.get("pe_ttm")
        return sd

    def close(self) -> None:
        self._session.close()


class _RetryableError(Exception):
    """标识可重试的临时错误（网络抖动、限流、服务端异常）。"""


def _full_thscode(code: str) -> str:
    """把 6 位纯代码转为完整 thscode（按交易所前缀推断）。"""
    code = code.strip().upper()
    if "." in code:
        return code  # 已是完整 thscode
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    # 沪市基金/ETF：50x/51x/56x/58x 等 5 开头（上交所场内基金）
    if code.startswith("5"):
        return f"{code}.SH"
    # 深市基金/ETF（LOF等）：15/16/18 开头（深交所场内基金）
    if code.startswith(("15", "16", "18")):
        return f"{code}.SZ"
    # 北交所股票：4x / 8x
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return f"{code}.SH"  # 兜底
