"""按精选股票集合（持仓/自选/观察）快速分析，避免全市场扫描。

用法：
    python scripts/analyze_collection.py [集合名]
    集合名: holdings | watchlist | observation | all   (默认 const/holdings 等可配置)

数据来源：同花顺官方金融数据服务（hithink-finance）REST API。
输出：表格（控制台）+ CSV（results/集合名.csv）。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from data_source.base import get_data_source


def resolve_collection_codes(cfg, key: str) -> list:
    """从 config 里取出对应集合的 code 列表。"""
    attr_map = {
        "holdings": "HOLDINGS",
        "watchlist": "WATCHLIST",
        "observation": "OBSERVATION",
    }
    data = getattr(cfg, attr_map[key], [])
    return data


def analyze(cfg, ds, key: str, label: str) -> list:
    items = resolve_collection_codes(cfg, key)
    if not items:
        print(f"[{label}] 集合为空，跳过。")
        return []

    codes = [it["code"] for it in items]
    print(f"\n=== {label}（{len(codes)} 只）===")

    quotes = ds.get_quotes_batch(codes)
    # 按集合内的顺序展示，并附上名称
    by_code = {q.code: q for q in quotes}
    rows = []
    for it in items:
        q = by_code.get(it["code"])
        if q is None:
            print(f"  {it['code']} {it.get('name','')}: 无行情数据")
            continue
        name = it.get("name") or q.name
        rows.append({
            "code": q.code,
            "name": name,
            "price": q.price,
            "change_pct": q.change_pct,
            "amount": q.amount,
            "pe_ttm": q.pe,
        })
        print(f"  {q.code} {name:<8s} 价格={q.price:<10.2f} "
              f"涨跌={q.change_pct:+.2f}% 成交额={q.amount/1e8:.2f}亿 PE={q.pe if q.pe is not None else '-'}")

    # 落盘
    import csv
    out = os.path.join("results", f"{key}.csv")
    os.makedirs("results", exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "price",
                                          "change_pct", "amount", "pe_ttm"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  已保存: {out}（{len(rows)} 行）")
    return rows


def main():
    parser = argparse.ArgumentParser(description="按集合快速分析持仓/自选/观察股")
    parser.add_argument("collection", nargs="?", default="all",
                        help="holdings|watchlist|observation|all")
    args = parser.parse_args()

    cfg = Config()
    if cfg.DATA_SOURCE != "hithink":
        print("提示：请设置 DATA_SOURCE=hithink 以使用同花顺官方数据。")
        print(f"当前为: {cfg.DATA_SOURCE}")
        return

    ds = get_data_source(cfg)
    if not ds.connect():
        print("连接同花顺数据服务失败。")
        return

    try:
        choice = args.collection
        keys = ["holdings", "watchlist", "observation"]
        if choice == "all":
            targets = keys
        elif choice in keys:
            targets = [choice]
        else:
            print(f"未知集合: {choice}，可选 {keys} 或 all")
            return
        for k in targets:
            analyze(cfg, ds, k, cfg.COLLECTIONS.get(k, k))
    finally:
        ds.close()


if __name__ == "__main__":
    main()
