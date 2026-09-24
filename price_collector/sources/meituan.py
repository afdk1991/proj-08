# -*- coding: utf-8 -*-
"""美团闪购数据源（真实抓取骨架）。

可抓取性评级：仅 App
入口 URL：https://waimai.meituan.com/ （美团外卖/闪购 PC 端）
空结果常见原因：
  - 美团闪购/外卖为 App 闭环业务，PC 网页 waimai.meituan.com 对无 Cookie 直接
    请求返回 403 Forbidden；商品列表、价格、店铺均需 App 登录态 + 定位（经纬度）。
  - mws.meituan.com（商家端）不对消费者开放且本机 DNS 不可达。
  - 静态 HTML 不含商品数据，本类尽力解析为骨架，未登录/未定位时返回 []。

生产建议：配置 PC_COOKIE_MEITUAN 并带上真实定位与 token，或改用 App 抓包 /
浏览器自动化方案。抓取失败一律返回空列表。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://waimai.meituan.com/search/{kw}"

# 美团商家/商品卡片内联 JSON 的尽力解析正则（随页面结构变化需同步更新）
_NAME_RE = re.compile(r'"(?:title|name|spuName|poiName)"\s*:\s*"([^"]+)"')
_PRICE_RE = re.compile(r'"(?:price|minPrice|wmPrice|spuPrice)"\s*:\s*"?([\d.]+)')
_ORIG_RE = re.compile(r'"(?:originPrice|originalPrice|currentBoxPrice)"\s*:\s*"?([\d.]+)')
_SHOP_RE = re.compile(r'"(?:shopName|poiName|brandName)"\s*:\s*"([^"]+)"')
_IMG_RE = re.compile(r'"(?:img|image|picUrl|icon)"\s*:\s*"(//[^"]+?)"')
_URL_RE = re.compile(r'"(?:poiId|spuId|itemId)"\s*:\s*"?(\d+)"')


class MeituanSource(BaseSource):
    platform = "meituan"
    platform_name = "美团闪购"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (
            cookie
            or os.environ.get("PC_COOKIE_MEITUAN")
            or os.environ.get("PC_COOKIE", "")
        )
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {"Referer": "https://waimai.meituan.com/"}
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
        shops = _SHOP_RE.findall(html)
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
                    url = "https://waimai.meituan.com/poi/" + str(ids[i])
                name = _strip_tags(names[i]) if i < len(names) else keyword
                shop = _strip_tags(shops[i]) if i < len(shops) else ""
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                result.append(Product(
                    platform="meituan",
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
