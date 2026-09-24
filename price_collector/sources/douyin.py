# -*- coding: utf-8 -*-
"""抖音电商数据源（真实抓取骨架）。

可抓取性评级：**需浏览器自动化**。
入口 URL：https://www.douyin.com/search/<kw>
空结果常见原因：抖音 PC 网页搜索为视频流为主，商品（抖音电商）多在 App /
抖音商城内闭环；PC 搜索页为强混淆 JS VM 渲染（_$jsvmprt 运行时），标准库静态
抓取只能拿到混淆脚本壳，无商品价格/标题数据。

本类提供真实请求构造与内嵌 JSON（title/price/product_id/cover/shop_name）解析骨架；
生产环境建议 Playwright 渲染或 App 抓包。异常吞掉返回空列表，由流水线回退示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_DOUYIN="sessionid=...; ttwid=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.douyin.com/search/{kw}?type=general&offset={offset}"

# 抖音搜索/商品卡内嵌 JSON 字段（_ROUTER_DATA 中）
_TITLE_RE = re.compile(r'"(?:title|aweme_title|product_title)"\s*:\s*"([^"]{2,120})"')
_PRICE_RE = re.compile(r'"(?:price|sale_price|discount_price)"\s*:\s*"?([\d.]+)"?')
_ORIG_RE = re.compile(r'"(?:origin_price|original_price)"\s*:\s*"?([\d.]+)"?')
_PROD_RE = re.compile(r'"(?:product_id|item_id)"\s*:\s*"?(\d{8,})"?')
_IMG_RE = re.compile(r'"(?:cover|img|cover_url)"\s*:\s*"(https?://[^"]+?)"')
_SHOP_RE = re.compile(r'"(?:shop_name|nickname)"\s*:\s*"([^"]{2,60})"')
_SALES_RE = re.compile(r'"(?:sales|sold_count|month_sold)"\s*:\s*"?(\d+(?:\.\d+)?)\s*(万)?"?')


class DouyinSource(BaseSource):
    platform = "douyin"
    platform_name = "抖音电商"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_DOUYIN") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        offset = (page - 1) * page_size
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), offset=offset)
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
        titles = _TITLE_RE.findall(html)
        prices = _PRICE_RE.findall(html)
        origs = _ORIG_RE.findall(html)
        prods = _PROD_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        shops = _SHOP_RE.findall(html)
        sales = _SALES_RE.findall(html)
        max_len = max(len(titles), len(prices), len(prods))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                pid = prods[i] if i < len(prods) else ""
                url = f"https://haohuo.jinritemai.com/views/product/item2?id={pid}" if pid else ""
                img = imgs[i] if i < len(imgs) else ""
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = _unescape(titles[i]) if i < len(titles) else keyword
                shop = _unescape(shops[i]) if i < len(shops) else ""
                sale_val = _http.parse_sales(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="douyin",
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
