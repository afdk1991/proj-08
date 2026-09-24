# -*- coding: utf-8 -*-
"""结果持久化：JSON / CSV 导出。"""
import csv
import json
import os
from typing import List, Dict, Any

from .models import SearchResult


def to_json(result: SearchResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


def save_json(result: SearchResult, path: str):
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)


def save_csv(result: SearchResult, path: str):
    _ensure_dir(path)
    fieldnames = [
        "platform", "name", "price", "original_price", "sales",
        "sales_text", "shop_rating", "shop_name", "score", "url",
    ]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        # 性价比分映射：用 recommendation 的 (name, price) 关联，避免同名商品误匹配
        score_map = {(r["name"], r["price"]): r.get("score") for r in result.recommendations}
        for p in result.sorted_products:
            row = {
                "platform": p.platform,
                "name": p.name,
                "price": p.price,
                "original_price": p.original_price,
                "sales": p.sales,
                "sales_text": p.sales_text,
                "shop_rating": p.shop_rating,
                "shop_name": p.shop_name,
                "score": score_map.get((p.name, p.price), ""),
                "url": p.url,
            }
            writer.writerow(row)


def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)