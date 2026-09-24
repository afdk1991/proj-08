# -*- coding: utf-8 -*-
"""性价比评分。

对一批商品计算 0~100 的「性价比分」，并给出推荐等级标注。

评分维度（透明、可解释）：
- 价格优势（weight 0.45）：在同批商品中越便宜得分越高
- 店铺口碑（weight 0.30）：店铺评分 0~5 归一化
- 销量热度（weight 0.25）：销量取 log1p 后归一化（销量越大越可信）

推荐等级：
- 性价比之王   : 同批前 10%
- 高性价比推荐 : 前 10%~30%
- 一般         : 其余
"""
import math
from typing import List, Dict


def _minmax(values: List[float]):
    if not values:
        return 0.0, 0.0
    lo, hi = min(values), max(values)
    return lo, hi


def _norm_inv(v, lo, hi):
    """价格越低得分越高。"""
    if hi == lo:
        return 1.0 if v <= lo else 0.0
    return 1.0 - (v - lo) / (hi - lo)


def _norm(v, lo, hi):
    if hi == lo:
        return 0.5
    return (v - lo) / (hi - lo)


def score_products(products: List) -> List[Dict]:
    """为一组商品计算性价比分，返回（推荐信息 dict 列表，含 product 引用）。"""
    if not products:
        return []

    prices = [p.price for p in products]
    ratings = [p.shop_rating if p.shop_rating >= 0 else 5.0 for p in products]
    # 销量归一化时对缺失销量做平滑（0 销量取 log1p(0)=0）
    sales_log = [math.log1p(max(p.sales, 0)) for p in products]

    p_lo, p_hi = _minmax(prices)
    r_lo, r_hi = _minmax(ratings)
    s_lo, s_hi = _minmax(sales_log)

    scored = []
    for i, p in enumerate(products):
        price_s = _norm_inv(prices[i], p_lo, p_hi)
        rating_s = _norm(ratings[i], r_lo, r_hi)
        sales_s = _norm(sales_log[i], s_lo, s_hi)
        score = 100 * (0.45 * price_s + 0.30 * rating_s + 0.25 * sales_s)
        scored.append({
            "product": p,
            "score": round(score, 1),
            "price_score": round(100 * price_s, 1),
            "rating_score": round(100 * rating_s, 1),
            "sales_score": round(100 * sales_s, 1),
        })

    # 按得分降序决定等级
    scored.sort(key=lambda x: x["score"], reverse=True)
    n = len(scored)
    top10 = max(1, int(n * 0.10))
    top30 = max(1, int(n * 0.30))
    for rank, item in enumerate(scored):
        if rank < top10:
            item["label"] = "性价比之王"
        elif rank < top30:
            item["label"] = "高性价比推荐"
        else:
            item["label"] = "一般"

    return scored


def build_recommendations(scored: List[Dict]) -> List[Dict]:
    """把评分结果转成可直接 JSON 序列化的推荐列表（按性价比分降序）。"""
    result = []
    for item in sorted(scored, key=lambda x: x["score"], reverse=True):
        p = item["product"]
        result.append({
            "rank": len(result) + 1,
            "name": p.name,
            "platform": p.platform,
            "price": p.price,
            "shop_rating": p.shop_rating,
            "sales": p.sales,
            "score": item["score"],
            "label": item["label"],
            "url": p.url,
        })
    return result