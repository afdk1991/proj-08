# -*- coding: utf-8 -*-
"""数据清洗与去重。

职责：
1. 归一化价格（去掉货币符号、千分位、""起"" 等后缀）
2. 归一化销量（"2.3万+" -> 23000）
3. 过滤无效条目（价格为 0 / 名称为空）
4. 去重（同一平台内按规范化名称 / URL 去重）
5. 剔除价格离群值（可选）
"""
import re
import statistics
from typing import List

from .models import Product


def _canonical_name(name: str) -> str:
    """生成用于去重的规范化名称：去空白、去标点、小写。"""
    t = re.sub(r"[\s\u3000]+", "", name)
    t = re.sub(r"[^\w\u4e00-\u9fff]+", "", t)
    return t.lower()


def normalize(product: Product) -> Product:
    """就地规范化一条商品的数值字段，返回该商品（方便链式调用）。"""
    product.name = (product.name or "").strip()
    product.price = round(float(product.price), 2)
    product.original_price = round(float(product.original_price or 0.0), 2)
    product.sales = int(product.sales or 0)
    product.shop_rating = round(float(product.shop_rating or -1.0), 1)
    product.shop_name = (product.shop_name or "").strip()
    product.url = (product.url or "").strip()
    return product


def clean(products: List[Product], dedup: bool = True,
          remove_outliers: bool = False, max_price: float = 0.0) -> List[Product]:
    """清洗、去重、过滤商品列表。

    :param dedup: 是否去重
    :param remove_outliers: 是否剔除价格离群值（基于 IQR，默认关闭，避免误删最低价好货）
    :param max_price: 若 > 0，则过滤掉超过该价格的商品
    """
    clean_list: List[Product] = []
    for p in products:
        normalize(p)
        if not p.name or p.price <= 0:
            continue
        clean_list.append(p)

    if dedup:
        clean_list = _dedup(clean_list)

    if remove_outliers and len(clean_list) >= 5:
        prices = [p.price for p in clean_list]
        q1 = statistics.quantiles(prices, n=4)[0]
        q3 = statistics.quantiles(prices, n=4)[2]
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        clean_list = [p for p in clean_list if lower <= p.price <= upper]

    if max_price > 0:
        clean_list = [p for p in clean_list if p.price <= max_price]

    return clean_list


def _dedup(products: List[Product]) -> List[Product]:
    """按「平台 + 规范化名称」去重；名称相同则保留价格更低的一条。"""
    seen = {}
    for p in products:
        key = (p.platform, _canonical_name(p.name))
        if key not in seen:
            seen[key] = p
        elif p.price < seen[key].price:
            seen[key] = p
    return list(seen.values())