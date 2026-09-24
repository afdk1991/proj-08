# -*- coding: utf-8 -*-
"""天猫数据源（真实抓取骨架）。

可抓取性评级：**需登录 Cookie**。
入口 URL：https://list.tmall.com/search_product.htm?q=<kw>&page=<page>
空结果常见原因：天猫搜索为 React/ICE 框架 SSR 壳 + 登录态校验，未配置有效
PC_COOKIE_TMALL 时静态 HTML 仅含框架上下文（window.__ICE_APP_CONTEXT__），
商品列表（title/price/itemId/shopName）走异步接口返回，静态抓取基本为空。

本类提供真实请求构造与内嵌 JSON 字段解析骨架；生产环境建议配登录 Cookie
或 Playwright 渲染。异常吞掉返回空列表，由流水线回退示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_TMALL="unb=...; cookie1=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://list.tmall.com/search_product.htm?q={kw}&s={offset}&page={page}"

# 天猫搜索结果内嵌 JSON 中的字段（title / price / itemId / shopName / picUrl / soldQuantity）
_TITLE_RE = re.compile(r'"title"\s*:\s*"([^"]{2,120})"')
_PRICE_RE = re.compile(r'"(?:price|priceWap|priceFloat)"\s*:\s*"?([\d.]+)"?')
_ORIG_RE = re.compile(r'"originalPrice"\s*:\s*"?([\d.]+)"?')
_ITEM_RE = re.compile(r'"(?:itemId|productId|auctionId)"\s*:\s*"?(\d{6,})"?')
_SHOP_RE = re.compile(r'"(?:shopName|shopTitle)"\s*:\s*"([^"]{2,60})"')
_IMG_RE = re.compile(r'"(?:picUrl|imgUrl|imageUrl)"\s*:\s*"(//[^"]+?)"')
_SALES_RE = re.compile(r'"(?:soldQuantity|soldCount|monthSold)"\s*:\s*"?(\d+(?:\.\d+)?)\s*(?:万)?"?')


class TmallSource(BaseSource):
    platform = "tmall"
    platform_name = "天猫"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_TMALL") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        offset = (page - 1) * page_size
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), offset=offset, page=page)
        headers = {"Referer": "https://www.tmall.com/"}
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
        items = _ITEM_RE.findall(html)
        shops = _SHOP_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        sales = _SALES_RE.findall(html)
        max_len = max(len(titles), len(prices), len(items))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                item = items[i] if i < len(items) else ""
                url = f"https://detail.tmall.com/item.htm?id={item}" if item else ""
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = _unescape(titles[i]) if i < len(titles) else keyword
                shop = _unescape(shops[i]) if i < len(shops) else ""
                sale_val = _http.parse_sales(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="tmall",
                    name=name,
                    price=p,
                    original_price=original,
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
