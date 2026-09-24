# -*- coding: utf-8 -*-
"""AliExpress 全球速卖通（阿里巴巴）数据源。

可抓取性评级：强反爬可能空结果。
入口 URL：https://www.aliexpress.com/wholesale?SearchText={kw}
空结果常见原因：
  - 站点启用阿里系 x5sec 风控（punish/滑块），未通过风控时静态抓取只返回
    一段跳登录/跳验证码的 JS（约 4KB），不含任何商品数据；
  - 偶发风控放行时，商品列表以内嵌 JSON 形式存在，本类对其做尽力解析。
本类仅做公开网页静态抓取，不做验证码破解/风控绕过；抓不到即返回空列表，
绝不外抛、不伪造数据。海外站价格以美元计，price 填页面原价数值。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.aliexpress.com/wholesale?SearchText={kw}&page={page}"

# 搜索结果内嵌 JSON 中的商品字段（随前端结构变化需同步更新）
_TITLE_RE = re.compile(r'"(?:title|productTitle|subject)"\s*:\s*"([^"]+)"')
_PRICE_RE = re.compile(r'"(?:salePrice|formattedPrice|price)"\s*:\s*"\$?\s*([\d.,]+)"')
_ORIG_RE = re.compile(r'"(?:originalPrice|formattedOriginalPrice|minPriceAfterDiscount)"\s*:\s*"\$?\s*([\d.,]+)"')
_SALES_RE = re.compile(r'"(?:tradeQuantity|sold|sales)"\s*:\s*"?(\d[\d.,]*[万kKmM]?)')
_URL_RE = re.compile(r'"(?:productDetailUrl|detailUrl|url)"\s*:\s*"(https?[^"]*?/item/[^"]+)"')
_IMG_RE = re.compile(r'"(?:imageUrl|image|imgUrl|mainImage)"\s*:\s*"(https?[^"]+\.(?:jpe?g|png|webp)[^"]*)"')


class AliexpressSource(BaseSource):
    platform = "aliexpress"
    platform_name = "AliExpress 全球速卖通"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_ALIEXPRESS") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page)
        headers = {"Referer": "https://www.aliexpress.com/"}
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
                    platform="aliexpress",
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
