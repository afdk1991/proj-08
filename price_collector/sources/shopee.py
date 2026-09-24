# -*- coding: utf-8 -*-
"""Shopee（Sea Group）数据源。

可抓取性评级：需浏览器自动化（JS 强渲染，静态 HTML 无数据）。
入口 URL：https://shopee.com/search?keyword={kw}
空结果常见原因：
  - 搜索结果为前端 SPA 客户端渲染，静态 HTML 只返回约 20KB 的应用壳，
    商品列表经由受签名/风控保护的 /api/v4/search 接口异步加载，
    无浏览器渲染时静态抓取拿不到商品数据；
  - 公开区选择 shopee.com（国际站），各分站点结构一致。
本类提供真实请求构造 + 内嵌 JSON 尽力解析骨架；抓不到即返回空列表，
绝不外抛、不伪造数据。海外站价格以美元计，price 填页面原价数值。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://shopee.com/search?keyword={kw}&page={page}"

# SPA 内若出现内嵌初始态 JSON，其商品字段形如（随前端结构变化需同步更新）
_TITLE_RE = re.compile(r'"name"\s*:\s*"([^"]{2,})"')
_PRICE_RE = re.compile(r'"(?:price|price_min|priceMax)"\s*:\s*([\d.]+)')
_ORIG_RE = re.compile(r'"(?:price_before_discount|original_price)"\s*:\s*([\d.]+)')
_SALES_RE = re.compile(r'"(?:historical_sold|sold|sales)"\s*:\s*"?(\d[\d.,]*)')
_URL_RE = re.compile(r'"(?:url|product_url)"\s*:\s*"(https?[^"]*?/product/[^"]+)"')
_IMG_RE = re.compile(r'"image"\s*:\s*"(https?[^"]+\.(?:jpe?g|png|webp)[^"]*)"')


class ShopeeSource(BaseSource):
    platform = "shopee"
    platform_name = "Shopee"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_SHOPEE") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page - 1)
        headers = {"Referer": "https://shopee.com/"}
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
        origs = _ORIG_RE.findall(html)
        sales = _SALES_RE.findall(html)
        urls = _URL_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        max_len = max(len(titles), len(prices))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                url = urls[i] if i < len(urls) else ""
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = _unescape(titles[i]) if i < len(titles) else keyword
                sale_text = sales[i] if i < len(sales) else ""
                result.append(Product(
                    platform="shopee",
                    name=name,
                    price=p,
                    original_price=original,
                    sales=_http.parse_sales(sale_text),
                    sales_text=sale_text,
                    shop_rating=-1.0,
                    shop_name="",
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
