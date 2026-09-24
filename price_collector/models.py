# -*- coding: utf-8 -*-
"""数据模型定义：商品条目、搜索结果、价格趋势点等。"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class Product:
    """一条清洗后的商品信息。"""
    platform: str            # 平台标识：jd / taobao / pdd
    name: str                # 商品名称
    price: float             # 当前价格（元）
    original_price: float    # 原价 / 划线价（元），缺失时为 0
    sales: int               # 销量（件），已归一化为整数
    sales_text: str          # 销量原始文案，如 "2.3万+"
    shop_rating: float       # 店铺评分 0~5，缺失时 -1
    shop_name: str           # 店铺名称
    url: str                 # 商品链接
    image: str               # 主图链接（可为空）
    keyword: str             # 采集所用关键词
    raw: Dict[str, Any] = field(default_factory=dict)  # 原始字段，便于溯源

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PricePoint:
    """价格趋势图上的一个数据点。"""
    rank: int                # 排序序号（按价格升序后的位置）
    price: float
    name: str
    platform: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlatformStat:
    """单平台统计汇总。"""
    platform: str
    count: int
    min_price: float
    max_price: float
    avg_price: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    """一次搜索的完整结果，可直接 JSON 序列化。"""
    keyword: str
    total: int
    products: List[Product]
    sorted_products: List[Product]            # 按价格升序
    price_trend: List[PricePoint]             # 价格趋势数据
    platform_stats: List[PlatformStat]        # 平台横向对比
    price_distribution: List[Dict[str, Any]]  # 价格区间分布
    recommendations: List[Dict[str, Any]]     # 性价比推荐
    source_mode: str                          # 固定为 live（已无示例/mock 路径）
    collected_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "total": self.total,
            "products": [p.to_dict() for p in self.sorted_products],
            "price_trend": [pt.to_dict() for pt in self.price_trend],
            "platform_stats": [ps.to_dict() for ps in self.platform_stats],
            "price_distribution": self.price_distribution,
            "recommendations": self.recommendations,
            "source_mode": self.source_mode,
            "collected_at": self.collected_at,
        }