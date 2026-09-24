# -*- coding: utf-8 -*-
"""快手电商数据源（真实抓取骨架）。

可抓取性评级：**需浏览器自动化**。
入口 URL：https://www.kuaishou.com/search?searchKey=<kw>
空结果常见原因：快手 PC 搜索为视频流 SPA（Next.js / Vite 构建），静态 HTML 仅含
CDN 调度与 UI 文案（window.__CDN_DISPATCH__），商品/视频列表（caption/photoUrl/
price/productId）由前端接口渲染，标准库静态抓取基本为空。

本类提供真实请求构造与内嵌 JSON 字段解析骨架；生产环境建议 Playwright 渲染或
App 抓包。异常吞掉返回空列表，由流水线回退示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_KUAISHOU="userId=...; kpf=PC_WEB; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.kuaishou.com/search?searchKey={kw}&page={page}"

# 快手搜索结果内嵌 JSON（__NEXT_DATA__ / search 接口）字段
_TITLE_RE = re.compile(r'"(?:caption|title|photoName)"\s*:\s*"([^"]{2,120})"')
_PRICE_RE = re.compile(r'"(?:price|salePrice|lowestPrice)"\s*:\s*"?([\d.]+)"?')
_PHOTO_RE = re.compile(r'"(?:photoId|headurl|photoIdH)"\s*:\s*"?(\d{8,})"?')
_IMG_RE = re.compile(r'"(?:thumbnailUrl|photoUrl|url)"\s*:\s*"(https?://[^"]+?\.(?:jpg|jpeg|png|webp))"')
_SHOP_RE = re.compile(r'"(?:name|sellerName)"\s*:\s*"([^"]{2,60})"')
_SALES_RE = re.compile(r'"(?:saleCount|sold|monthSell)"\s*:\s*"?(\d+(?:\.\d+)?)\s*(万)?"?')


class KuaishouSource(BaseSource):
    platform = "kuaishou"
    platform_name = "快手电商"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_KUAISHOU") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page)
        headers = {"Referer": "https://www.kuaishou.com/"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        try:
            html = _http.fetch_html(url, timeout=self.timeout, headers=headers)
        except Exception:
            return []
        return self._parse(html, keyword)[:page_size]

    @staticmethod
    def _parse(html: str, keyword: str) -> List[Product]:
        result: List[Product] = []
        titles = _TITLE_RE.findall(html)
        prices = _PRICE_RE.findall(html)
        photos = _PHOTO_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        shops = _SHOP_RE.findall(html)
        sales = _SALES_RE.findall(html)
        max_len = max(len(titles), len(prices), len(photos))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                pid = photos[i] if i < len(photos) else ""
                url = f"https://www.kuaishou.com/short-video/{pid}" if pid else ""
                img = imgs[i] if i < len(imgs) else ""
                name = _unescape(titles[i]) if i < len(titles) else keyword
                shop = _unescape(shops[i]) if i < len(shops) else ""
                sale_val = _http.parse_sales(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="kuaishou",
                    name=name,
                    price=p,
                    original_price=0.0,
                    sales=sale_val,
                    sales_text=sales[i] if i < len(sales) else "",
                    shop_rating=-1.0,
                    shop_name=shop,
                    url=url,
                    image=img,
                    keyword=keyword,
                    raw={},
                ))
            except Exception:
                continue
        return result


def _unescape(s: str) -> str:
    return (s or "").replace("\\u003c", "<").replace("\\/", "/").replace("\\\"", "\"").strip()
