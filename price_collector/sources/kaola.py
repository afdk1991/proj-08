# -*- coding: utf-8 -*-
"""考拉海购（Kaola / 阿里巴巴）数据源（真实抓取骨架）。

可抓取性评级：强反爬可能空结果
入口 URL：https://www.kaola.com/search.html?searchValue={关键词}
说明：考拉海购已并入阿里系，搜索结果为 JS 动态渲染；且在本机当前网络环境下
www.kaola.com 域名 DNS 解析即失败（getaddrinfo failed），静态抓取直接抛
异常。本类给出真实搜索入口 URL 与商品字段解析骨架；空结果常见原因：
当前网络无法解析 kaola.com / 域名已迁移、搜索结果走前端 JS 渲染、或需登录
Cookie（PC_COOKIE_KAOLA）。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.kaola.com/search.html?searchValue={kw}"

# 考拉搜索页常见内嵌/卡片字段（随页面结构变化需同步更新）
_NAME_RE = re.compile(r'"(?:productName|title|goodsName)"\s*:\s*"(.*?)"')
_PRICE_RE = re.compile(r'"(?:price|salePrice|netPrice)"\s*:\s*"?([\d.]+)"')
_ORIG_RE = re.compile(r'"(?:originPrice|originalPrice)"\s*:\s*"?([\d.]+)"')
_URL_RE = re.compile(r'"(?:productUrl|itemUrl|goodsUrl)"\s*:\s*"([^"]+)"')
_IMG_RE = re.compile(r'"(?:image|picUrl|imgUrl)"\s*:\s*"([^"]+)"')


class KaolaSource(BaseSource):
    platform = "kaola"
    platform_name = "考拉海购"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (cookie or os.environ.get("PC_COOKIE_KAOLA")
                       or os.environ.get("PC_COOKIE", ""))
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {"Referer": "https://www.kaola.com/"}
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
                url = urls[i] if i < len(urls) else ""
                if url and url.startswith("//"):
                    url = "https:" + url
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = names[i] if i < len(names) else keyword
                result.append(Product(
                    platform="kaola",
                    name=name,
                    price=p,
                    original_price=original,
                    sales=0,
                    sales_text="",
                    shop_rating=-1.0,
                    shop_name="考拉海购",
                    url=url,
                    image=img,
                    keyword=keyword,
                    raw={},
                ))
            except Exception:
                continue
        return result
