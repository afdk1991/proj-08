# -*- coding: utf-8 -*-
"""天猫国际（Tmall.HK / 阿里巴巴）数据源（真实抓取骨架）。

可抓取性评级：需登录 Cookie
入口 URL：https://www.tmall.hk/search/search_product.htm?q={关键词}
说明：天猫国际首页（www.tmall.hk）可静态访问，但其搜索结果页已迁移至阿里
WOW（pages.tmall.com）SPA，旧 search_product 静态入口现已 404，且搜索结果
为 JS 动态渲染 + 阿里统一登录/反爬（未登录通常仅返回壳页面或跳转登录）。
本类给出真实的请求构造与内嵌 JSON 字段解析骨架；空结果常见原因：
未登录 Cookie、搜索结果走前端 JS 渲染、或被风控跳转登录页。生产建议配
PC_COOKIE_TMALLGLOBAL 或改用浏览器渲染。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.tmall.hk/search/search_product.htm?q={kw}&page={page}"

# 天猫/淘宝系搜索页内嵌 JSON 中的常见字段（随页面结构变化需同步更新）
_TITLE_RE = re.compile(r'"raw_title"\s*:\s*"(.*?)"')
_PRICE_RE = re.compile(r'"price"\s*:\s*"?([\d.]+)"')
_ORIG_RE = re.compile(r'"origPrice"\s*:\s*"?([\d.]+)"')
_URL_RE = re.compile(r'"detail_url"\s*:\s*"(.*?)"')
_IMG_RE = re.compile(r'"pic_url"\s*:\s*"([^"]+)"')
_SHOP_RE = re.compile(r'"shop_name"\s*:\s*"(.*?)"')


class TmallglobalSource(BaseSource):
    platform = "tmallglobal"
    platform_name = "天猫国际"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (cookie or os.environ.get("PC_COOKIE_TMALLGLOBAL")
                       or os.environ.get("PC_COOKIE", ""))
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page)
        headers = {"Referer": "https://www.tmall.hk/"}
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
        urls = _URL_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        shops = _SHOP_RE.findall(html)
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
                name = _strip_tags(titles[i]) if i < len(titles) else keyword
                shop = shops[i] if i < len(shops) else ""
                result.append(Product(
                    platform="tmallglobal",
                    name=name,
                    price=p,
                    original_price=original,
                    sales=0,
                    sales_text="",
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


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()
