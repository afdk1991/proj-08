# -*- coding: utf-8 -*-
"""盒马（freshhema.com）数据源（真实抓取骨架）。

可抓取性评级：需浏览器自动化
入口 URL：https://www.freshhema.com/search?keyword={kw}
空结果常见原因：
  - 盒马为阿里系同城即时配送业务，搜索页由前端 JS 强渲染（页面含 aplus 埋点脚本），
    静态 HTML 仅约 2KB 壳，不含商品列表。
  - 真实商品数据经内部 mtop API 异步拉取，需登录态 + 定位（门店/经纬度）+ 签名。
  - 未满足上述条件时静态抓取返回 []，属预期。

生产建议：配置 PC_COOKIE_HEMA + 门店定位，或改用 App 抓包 / 浏览器自动化。
抓取失败一律返回空列表。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.freshhema.com/search?keyword={kw}"

# 盒马商品卡片内联 JSON 的尽力解析正则
_NAME_RE = re.compile(r'"(?:name|itemName|spuName|title)"\s*:\s*"([^"]+)"')
_PRICE_RE = re.compile(r'"(?:price|salePrice|currentPrice|exclusivePrice)"\s*:\s*"?([\d.]+)')
_ORIG_RE = re.compile(r'"(?:originPrice|originalPrice|linePrice)"\s*:\s*"?([\d.]+)')
_IMG_RE = re.compile(r'"(?:img|image|picUrl|imgUrl)"\s*:\s*"(//[^"]+?)"')
_URL_RE = re.compile(r'"(?:itemId|spuId|skuId)"\s*:\s*"?(\d+)"')


class HemaSource(BaseSource):
    platform = "hema"
    platform_name = "盒马"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (
            cookie
            or os.environ.get("PC_COOKIE_HEMA")
            or os.environ.get("PC_COOKIE", "")
        )
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {"Referer": "https://www.freshhema.com/"}
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
        imgs = _IMG_RE.findall(html)
        ids = _URL_RE.findall(html)
        for i, price in enumerate(prices[:50]):
            try:
                p = _http.parse_price(price)
                if p <= 0:
                    continue
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                url = ""
                if i < len(ids):
                    url = "https://www.freshhema.com/item/" + str(ids[i])
                name = _strip_tags(names[i]) if i < len(names) else keyword
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                result.append(Product(
                    platform="hema",
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


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()
