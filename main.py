"""选股程序入口。

运行方式（在项目根目录）：
    python main.py
"""
from config import Config
from pipeline import StockSelectionPipeline
from utils.output import save_results


def main():
    # 1. 加载配置
    cfg = Config()

    # 2. 创建并运行选股流水线
    pipeline = StockSelectionPipeline(cfg)
    stocks = pipeline.run()

    # 3. 输出结果
    if not stocks:
        print("没有筛选出符合条件的股票。")
        return

    filepath = save_results(stocks, cfg.OUTPUT_FILE)
    print(f"\n选股完成，共 {len(stocks)} 只，结果已保存到: {filepath}")
    for sd in stocks[:20]:
        print(f"  {sd.code} {sd.name}  @ {sd.price}")


if __name__ == "__main__":
    main()
