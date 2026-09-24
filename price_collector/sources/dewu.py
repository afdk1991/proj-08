# -*- coding: utf-8 -*-
"""得物（上海识装）数据源（真实抓取骨架）。

可抓取性评级：需浏览器自动化
入口 URL：https://www.dewu.com/search?q={kw}
空结果常见原因：
  - 得物 PC 搜索为 Next.js 客户端渲染，静态 HTML 中 __NEXT_DATA__ 的
    product 数组为空（实测 isServer 返回空列表），商品数据由前端异步请求内部接口。
  - 内部接口需风控 token / 签名，静态抓取拿不到列表。
  - 满足渲染/签名条件前本类返回 []，属预期。

生产建议：配置 PC_COOKIE_DEWU 或改用 Playwright 渲染。抓取失败一律返回空列表。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.dewu.com/search?q={kw}"

# 得物商品卡片内联 JSON 的尽力解析正则
_NAME_RE = re.compile(r'"(?:title|spuName|name)"\s*:\s*"([^"]+)"')
_PRICE_RE = re.compile(r'"(?:price|spuPrice|salePrice|minPrice)"\s*:\s*"?([\d.]+)')
_ORIG_RE = re.compile(r'"(?:originPrice|originalPrice|marketPrice)"\s*:\s*"?([\d.]+)')
_IMG_RE = re.compile(r'"(?:imgUrl|image|picUrl|mainImg)"\s*:\s*"(//[^"]+?)"')
_URL_RE = re.compile(r'"(?:spuId|itemId|goodsId)"\s*:\s*"?(\d+)"')


class DewuSource(BaseSource):
    platform = "dewu"
    platform_name = "得物"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (
            cookie
            or os.environ.get("PC_COOKIE_DEWU")
            or os.environ.get("PC_COOKIE", "")
        )
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {"Referer": "https://www.dewu.com/"}
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
                    url = "https://www.dewu.com/detail/" + str(ids[i])
                name = _strip_tags(names[i]) if i < len(names) else keyword
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                result.append(Product(
                    platform="dewu",
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
