# -*- coding: utf-8 -*-
"""Temu（PDD Holdings，出海站）数据源（真实抓取骨架）。

可抓取性评级：需浏览器自动化
入口 URL：https://www.temu.com/search_result.html?search_key={关键词}
说明：Temu 搜索页返回 200（约 287KB），但仅为 SPA 壳：window.rawData /
window.__SSR__ 只含 region/currency 等 Redux 配置，商品列表由前端 JS 调用
带签名的 FaaS 搜索接口异步拉取，静态 HTML 中无 goodsName/price 字段。价格
单位为美元（USD），按规范解析后 price 字段直接取页面原价数值即可。空结果
常见原因：JS 强渲染静态无数据、触发风控（页面含 verify/captcha）、需登录
Cookie（PC_COOKIE_TEMU）或浏览器自动化（Playwright）。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.temu.com/search_result.html?search_key={kw}"

# Temu 商品卡片内嵌字段（PC 静态壳通常无命中，仅作骨架）
_NAME_RE = re.compile(r'"(?:goodsName|title|goods_name)"\s*:\s*"(.*?)"')
_PRICE_RE = re.compile(r'"(?:salePrice|price|priceStr)"\s*:\s*"?\$?\s*([\d.]+)"')
_ORIG_RE = re.compile(r'"(?:marketPrice|originPrice|priceBeforeDiscount)"\s*:\s*"?\$?\s*([\d.]+)"')
_URL_RE = re.compile(r'"(?:goodsId|goods_id)"\s*:\s*"?(\d+)"')
_IMG_RE = re.compile(r'"(?:image|imageUrl|thumbUrl)"\s*:\s*"([^"]+)"')


class TemuSource(BaseSource):
    platform = "temu"
    platform_name = "Temu"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (cookie or os.environ.get("PC_COOKIE_TEMU")
                       or os.environ.get("PC_COOKIE", ""))
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {
            "Referer": "https://www.temu.com/",
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
                gid = urls[i] if i < len(urls) else ""
                url = ("https://www.temu.com/dp/p-%s.html" % gid) if gid else ""
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = names[i] if i < len(names) else keyword
                result.append(Product(
                    platform="temu",
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
