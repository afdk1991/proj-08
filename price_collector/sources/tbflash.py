# -*- coding: utf-8 -*-
"""淘宝闪购·小时达数据源（真实抓取骨架）。

可抓取性评级：仅 App
入口 URL：https://s.taobao.com/search?q={kw} （小时达/闪购为淘宝 App 内一级 Tab）
空结果常见原因：
  - “淘宝小时达”已于 2025 年升级为“淘宝闪购”，与饿了么打通，是淘宝 App 内的
    同城即时配送一级入口，PC 网页无独立商品搜索端点。
  - 营销落地页 https://www.taobao.com/markets/flash 在无登录态下直接跳 error 页，
    不含商品列表。
  - 底层搜索复用淘宝 s.taobao.com，受淘宝强反爬（登录 Cookie / 滑块 / mtop 签名）
    影响，静态 HTML 无结果，属预期。

生产建议：在淘宝 App 内抓包，或配置 PC_COOKIE_TBFLASH + 浏览器自动化。
抓取失败一律返回空列表。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://s.taobao.com/search?q={kw}"

# 复用淘宝搜索页内嵌 JSON（g_page_config / auctions）字段
_TITLE_RE = re.compile(r'"raw_title"\s*:\s*"([^"]+)"')
_PRICE_RE = re.compile(r'"view_price"\s*:\s*"([\d.]+)"')
_SALES_RE = re.compile(r'"comment_count"\s*:\s*"?([\d.万亿+]+)"?')
_SHOP_RE = re.compile(r'"shop_name"\s*:\s*"([^"]+)"')
_URL_RE = re.compile(r'"detail_url"\s*:\s*"([^"]+)"')
_IMG_RE = re.compile(r'"pic_url"\s*:\s*"([^"]+)"')


class TbflashSource(BaseSource):
    platform = "tbflash"
    platform_name = "淘宝闪购·小时达"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (
            cookie
            or os.environ.get("PC_COOKIE_TBFLASH")
            or os.environ.get("PC_COOKIE", "")
        )
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {"Referer": "https://www.taobao.com/"}
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
        sales = _SALES_RE.findall(html)
        shops = _SHOP_RE.findall(html)
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
                name = _unescape(titles[i]) if i < len(titles) else keyword
                shop = _unescape(shops[i]) if i < len(shops) else ""
                sale_val = _http.parse_sales(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="tbflash",
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
