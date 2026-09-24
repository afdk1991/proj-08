# -*- coding: utf-8 -*-
"""对比分析与可视化数据准备。

产出：
- 价格趋势：按价格升序的折线数据点
- 平台横向对比：各平台数量/最低/最高/均价
- 价格区间分布：用于柱状图
"""
from typing import List
from collections import defaultdict

from .models import Product, PricePoint, PlatformStat
from .sources.registry import ALL_PLATFORMS, PLATFORM_NAMES

# 平台顺序/名称从权威注册表派生，覆盖全部平台；有数据的才会进 stats
PLATFORM_ORDER = list(ALL_PLATFORMS)


def sort_by_price(products: List[Product]) -> List[Product]:
    """按价格从低到高排序（同价按销量降序）。"""
    return sorted(products, key=lambda p: (p.price, -p.sales))


def build_price_trend(sorted_products: List[Product]) -> List[PricePoint]:
    """生成价格趋势折线数据点。"""
    return [
        PricePoint(rank=i + 1, price=p.price, name=p.name, platform=p.platform)
        for i, p in enumerate(sorted_products)
    ]


def build_platform_stats(products: List[Product]) -> List[PlatformStat]:
    """按平台汇总统计（横向对比）。"""
    groups = defaultdict(list)
    for p in products:
        groups[p.platform].append(p.price)

    stats = []
    for platform in PLATFORM_ORDER:
        prices = groups.get(platform, [])
        if not prices:
            continue
        stats.append(PlatformStat(
            platform=platform,
            count=len(prices),
            min_price=round(min(prices), 2),
            max_price=round(max(prices), 2),
            avg_price=round(sum(prices) / len(prices), 2),
        ))
    return stats


def build_price_distribution(products: List[Product], buckets: int = 8) -> List[dict]:
    """把价格等距分为若干区间，统计每个区间的商品数。"""
    if not products:
        return []
    prices = [p.price for p in products]
    lo, hi = min(prices), max(prices)
    if hi == lo:
        # 单一价格：单桶
        return [{"range": f"{lo:.2f}", "min": lo, "max": hi, "count": len(products)}]

    step = (hi - lo) / buckets
    bins = [0] * buckets
    for price in prices:
        idx = min(int((price - lo) / step), buckets - 1)
        bins[idx] += 1

    result = []
    for i in range(buckets):
        b_lo = lo + i * step
        b_hi = lo + (i + 1) * step
        result.append({
            "range": f"{b_lo:.0f}-{b_hi:.0f}",
            "min": round(b_lo, 2),
            "max": round(b_hi, 2),
            "count": bins[i],
        })
    return result


def summarize(products: List[Product]) -> dict:
    """综合统计摘要（最低/最高/均价/中位数等）。"""
    if not products:
        return {"count": 0}
    prices = [p.price for p in products]
    prices_sorted = sorted(prices)
    n = len(prices_sorted)
    median = prices_sorted[n // 2] if n % 2 else (prices_sorted[n // 2 - 1] + prices_sorted[n // 2]) / 2
    return {
        "count": n,
        "min_price": round(min(prices), 2),
        "max_price": round(max(prices), 2),
        "avg_price": round(sum(prices) / n, 2),
        "median_price": round(median, 2),
    }