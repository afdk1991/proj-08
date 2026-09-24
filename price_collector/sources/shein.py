# -*- coding: utf-8 -*-
"""SHEIN（出海站）数据源（真实抓取骨架）。

可抓取性评级：强反爬可能空结果
入口 URL：https://www.shein.com/new/search.html?Search={关键词}
说明：SHEIN 搜索页（含 /new/search.html?Search= 与 /pdsearch/ 两种形态）
在标准 UA 直连下直接返回 HTTP 403 Forbidden（实测中英文语言区均 403），
其 CDN/WAF 对未通过反爬校验的请求不放行静态 HTML，因此拿不到任何商品列表。
价格单位为美元（USD），按规范解析后 price 字段直接取页面原价数值。空结果
常见原因：被 Cloudflare/WAF 拦截 403、JS 强渲染、需登录 Cookie
（PC_COOKIE_SHEIN）或浏览器自动化。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.shein.com/new/search.html?Search={kw}"

# SHEIN 商品卡片内嵌字段（被 WAF 拦截时恒无命中，仅作骨架）
_NAME_RE = re.compile(r'"(?:goodsName|name|goods_name)"\s*:\s*"(.*?)"')
_PRICE_RE = re.compile(r'"(?:salePrice|price|retailPrice)"\s*:\s*"?\$?\s*([\d.]+)"')
_ORIG_RE = re.compile(r'"(?:originPrice|marketPrice|taxIncludeMarketPrice)"\s*:\s*"?\$?\s*([\d.]+)"')
_URL_RE = re.compile(r'href="(/[^"]*-i-(\d+)-s-\d+\.html)"')
_IMG_RE = re.compile(r'"(?:imageUrl|goodsImg|thumbnail)"\s*:\s*"([^"]+)"')


class SheinSource(BaseSource):
    platform = "shein"
    platform_name = "SHEIN"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (cookie or os.environ.get("PC_COOKIE_SHEIN")
                       or os.environ.get("PC_COOKIE", ""))
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {
            "Referer": "https://www.shein.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }
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
        names = _NAME_RE.findall(html)
        prices = _PRICE_RE.findall(html)
        origs = _ORIG_RE.findall(html)
        urls = _URL_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        for i, price in enumerate(prices[:50]):
            try:
                p = _http.parse_price(price)
                if p <= 0:
                    continue
                url = ("https://www.shein.com" + urls[i][0]) if i < len(urls) else ""
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = names[i] if i < len(names) else keyword
                result.append(Product(
                    platform="shein",
                    name=name,
                    price=p,
                    original_price=original,
                    sales=0,
                    sales_text="",
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
