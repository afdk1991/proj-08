# -*- coding: utf-8 -*-
"""抖音全球购（Douyin Global Shopping / 字节跳动）数据源（真实抓取骨架）。

可抓取性评级：仅 App
入口 URL：https://www.douyin.com/search/{关键词}
说明：抖音电商以 App / 直播 / 推荐流为主，PC 网页搜索（douyin.com/search）
虽可返回 200，但静态 HTML 仅为 SPA 壳（实测 ~72KB，无商品卡片、无价格/
店铺字段），商品列表完全由前端 JS 调用带签名的接口渲染，且全球购/跨境商品
在 PC 端基本不开放搜索。静态抓取结果恒为空。空结果常见原因：PC 网页无商品
搜索结果、需 App / 登录 Cookie（PC_COOKIE_DOUYINGLOBAL）/ 浏览器自动化。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.douyin.com/search/{kw}"

# 抖音搜索/商品流内嵌字段（PC 静态页通常无命中，仅作骨架）
_NAME_RE = re.compile(r'"(?:aweme_title|desc|product_name)"\s*:\s*"(.*?)"')
_PRICE_RE = re.compile(r'"(?:price|sale_price)"\s*:\s*"?([\d.]+)"')
_URL_RE = re.compile(r'"(?:aweme_id|product_id)"\s*:\s*"?(\d+)"')
_IMG_RE = re.compile(r'"(?:cover|img_url)"\s*:\s*"([^"]+)"')


class DouyinglobalSource(BaseSource):
    platform = "douyinglobal"
    platform_name = "抖音全球购"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (cookie or os.environ.get("PC_COOKIE_DOUYINGLOBAL")
                       or os.environ.get("PC_COOKIE", ""))
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {"Referer": "https://www.douyin.com/"}
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
        urls = _URL_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        for i, price in enumerate(prices[:50]):
            try:
                p = _http.parse_price(price)
                if p <= 0:
                    continue
                pid = urls[i] if i < len(urls) else ""
                url = ("https://www.douyin.com/video/%s" % pid) if pid else ""
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                name = names[i] if i < len(names) else keyword
                result.append(Product(
                    platform="douyinglobal",
                    name=name,
                    price=p,
                    original_price=0.0,
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
