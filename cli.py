# -*- coding: utf-8 -*-
"""命令行工具入口。

用法示例：
    python cli.py search 蓝牙耳机                          # 真实抓取全部平台，按价格排序
    python cli.py search 蓝牙耳机 --platform jd taobao     # 指定平台
    python cli.py search 蓝牙耳机 --page 2 --size 30        # 翻页 / 每平台条数
    python cli.py search 蓝牙耳机 --output data/out.json    # 指定输出路径
    python cli.py search 蓝牙耳机 --format csv              # 导出 CSV
"""
import argparse
import sys
import os

# 保证 Windows 控制台 UTF-8 输出
for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass

from price_collector import pipeline, storage
from price_collector.sources import PLATFORM_NAMES
from price_collector.sources.registry import ALL_PLATFORMS


def _print_result(result):
    print("=" * 82)
    print(f"关键词: {result.keyword}   |   数据源: {result.source_mode}   |   共 {result.total} 条")
    print("=" * 82)
    if not result.products:
        print("（无结果）")
        return
    header = f"{'排名':<4} {'平台':<4} {'价格(¥)':<10} {'原价(¥)':<10} {'销量':<8} {'评分':<6} 商品名称"
    print(header)
    print("-" * 82)
    for i, p in enumerate(result.products, 1):
        plat = PLATFORM_NAMES.get(p.platform, p.platform)
        sales_s = p.sales_text or str(p.sales)
        rating_s = f"{p.shop_rating}" if p.shop_rating >= 0 else "-"
        name = p.name if len(p.name) <= 34 else p.name[:33] + "…"
        print(f"{i:<4} {plat:<4} {p.price:<10.2f} {p.original_price:<10.2f} {sales_s:<8} {rating_s:<6} {name}")
    print("-" * 82)
    print("【性价比推荐 Top 5】")
    for r in result.recommendations[:5]:
        plat = PLATFORM_NAMES.get(r["platform"], r["platform"])
        print(f"  {r['rank']}. [{r['label']}] ({plat}) {r['name'][:30]}  ¥{r['price']}  性价比分 {r['score']}")
    print("=" * 82)


def cmd_search(args):
    result = pipeline.run(
        keyword=args.keyword,
        platforms=args.platform,
        source_mode=args.source,
        page=args.page,
        page_size=args.size,
        sort_by=args.sort,
    )
    _print_result(result)

    # 输出文件
    out = args.output
    if not out:
        safe = "".join(c for c in args.keyword if c.isalnum() or c in "-_")
        out = os.path.join("data", f"result_{safe or 'output'}.json")
    if args.format == "csv":
        out = out.rsplit(".", 1)[0] + ".csv" if out.endswith(".json") else out
        storage.save_csv(result, out)
    else:
        if not out.endswith(".json"):
            out += ".json"
        storage.save_json(result, out)
    print(f"\n结果已保存: {os.path.abspath(out)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="price_collector",
        description="电商商品价格自动化采集与对比工具",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="按关键词搜索采集（真实抓取）")
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--platform", nargs="+", choices=ALL_PLATFORMS,
                          default=None, help="平台（默认全部已注册平台）")
    p_search.add_argument("--source", choices=["live"], default="live",
                          help="数据源模式（仅真实抓取 live）")
    p_search.add_argument("--page", type=int, default=1, help="页码")
    p_search.add_argument("--size", type=int, default=20, help="每平台条数")
    p_search.add_argument("--sort", default="price", help="排序字段")
    p_search.add_argument("--output", default=None, help="输出文件路径")
    p_search.add_argument("--format", choices=["json", "csv"], default="json", help="输出格式")
    p_search.set_defaults(func=cmd_search)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()