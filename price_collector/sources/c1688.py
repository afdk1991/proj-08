# -*- coding: utf-8 -*-
"""1688 数据源（真实抓取骨架）。

可抓取性评级：**需登录 Cookie**。
入口 URL：https://s.1688.com/selloffer/offer_search.htm?keywords=<kw>
空结果常见原因：1688 搜索未登录时会被 302 重定向到登录页（login.1688.com/member/
signin.htm），静态抓取只能拿到跳转脚本（约 5KB）；商品列表（title/priceInfo/offerId/
imgUrl/companyName）需登录态接口返回。

本类提供真实请求构造与内嵌 JSON 字段解析骨架；生产环境建议配有效 PC_COOKIE_1688
或 Playwright 渲染。异常吞掉返回空列表，由流水线回退示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_1688="cookie1=...; __cn_logon__=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm?keywords={kw}&beginPage={page}"

# 1688 搜索结果内嵌 JSON（offer_search_result / smOffers）中的字段
_TITLE_RE = re.compile(r'"title"\s*:\s*"([^"]{2,120})"')
_PRICE_RE = re.compile(r'"(?:priceInfo|price|displayPrice)"\s*:\s*"?([\d.]+(?:\.\d+)?)"?')
_OFFER_RE = re.compile(r'"(?:offerId|id|offer_id)"\s*:\s*"?(\d{8,})"?')
_IMG_RE = re.compile(r'"(?:imgUrl|imageUrl|picUrl)"\s*:\s*"(//[^"]+?)"')
_SHOP_RE = re.compile(r'"(?:companyName|memberName|shopName)"\s*:\s*"([^"]{2,60})"')
_SALES_RE = re.compile(r'"(?:saleCount|soldQuantity|monthSold)"\s*:\s*"?(\d+(?:\.\d+)?)\s*(万)?"?')


class C1688Source(BaseSource):
    platform = "c1688"
    platform_name = "1688"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_1688") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page)
        headers = {"Referer": "https://www.1688.com/"}
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
        offers = _OFFER_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        shops = _SHOP_RE.findall(html)
        sales = _SALES_RE.findall(html)
        max_len = max(len(titles), len(prices), len(offers))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                oid = offers[i] if i < len(offers) else ""
                url = f"https://detail.1688.com/offer/{oid}.html" if oid else ""
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                name = _unescape(titles[i]) if i < len(titles) else keyword
                shop = _unescape(shops[i]) if i < len(shops) else ""
                sale_val = _http.parse_sales(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="c1688",
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
