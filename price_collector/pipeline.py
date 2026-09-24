# -*- coding: utf-8 -*-
"""采集流水线：拉取 -> 清洗去重 -> 排序 -> 评分 -> 组装结果。

这是整个工具的编排核心，只依赖 BaseSource 接口。
本版本已彻底移除示例/mock 数据路径：唯一真实采集方式为 live。
零结果时返回空 products + total 0 + source_mode "live"，绝不伪造数据。
"""
import os
from datetime import datetime
from typing import List, Optional

from .models import SearchResult, Product
from .sources.base import SourceFactory
from .sources.registry import ALL_PLATFORMS
from . import cleaning, scoring, analysis


def _ensure_registry():
    SourceFactory.init_registry()


def run(
    keyword: str,
    platforms: Optional[List[str]] = None,
    source_mode: str = "live",
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "price",
    dedup: bool = True,
) -> SearchResult:
    """执行一次完整采集。

    :param keyword: 搜索关键词
    :param platforms: 平台列表，默认全部已注册平台
    :param source_mode: 历史参数；现仅真实抓取 live。任何取值都按 live 处理，
                        以保证前端契约字段稳定。
    :param page: 页码
    :param page_size: 每平台条数
    :param sort_by: 排序方式，目前按 price
    """
    _ensure_registry()
    keyword = (keyword or "").strip()

    # 仅保留已注册且请求合法的平台；非法平台直接跳过（不抛错给用户）
    known = set(SourceFactory.available())
    if platforms:
        platforms = [p for p in platforms if p in known]
    if not platforms:
        platforms = list(known)

    raw: List[Product] = _fetch_live(keyword, platforms, page, page_size)

    # 清洗去重（默认不剔除离群值，保留全部价格样本，包括最便宜的好货）
    cleaned = cleaning.clean(raw, dedup=dedup, remove_outliers=False)

    # 排序（价格从低到高）
    sorted_products = analysis.sort_by_price(cleaned)

    # 性价比评分与推荐
    scored = scoring.score_products(sorted_products)
    recommendations = scoring.build_recommendations(scored)

    # 分析数据
    price_trend = analysis.build_price_trend(sorted_products)
    platform_stats = analysis.build_platform_stats(sorted_products)
    distribution = analysis.build_price_distribution(sorted_products)

    return SearchResult(
        keyword=keyword,
        total=len(sorted_products),
        products=sorted_products,
        sorted_products=sorted_products,
        price_trend=price_trend,
        platform_stats=platform_stats,
        price_distribution=distribution,
        recommendations=recommendations,
        source_mode="live",
        collected_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def _fetch_live(keyword: str, platforms: List[str], page: int, page_size: int) -> List[Product]:
    """并发抓取各平台；不传入全局 cookie，各源自行读取 PC_COOKIE_<KEY> / PC_COOKIE。

    用线程池并发跑所有平台，总耗时 ≈ 最慢一个源（而非 N 个之和），
    避免云端函数因串行超时触发 504。单源失败/被拦截一律返回 []，不影响其它源。
    """
    try:
        timeout = int(os.environ.get("PC_TIMEOUT", "10"))
    except ValueError:
        timeout = 10

    def _fetch_one(pf: str):
        try:
            src = SourceFactory.create(pf, timeout=timeout)
            if not src.can_live():
                return []
            return src.fetch(keyword, page=page, page_size=page_size)
        except Exception:
            return []

    from concurrent.futures import ThreadPoolExecutor
    products: List[Product] = []
    workers = min(len(platforms), 16) if platforms else 1
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(_fetch_one, platforms):
            products.extend(res)
    return products
