# -*- coding: utf-8 -*-
"""淘宝数据源（真实抓取骨架）。

可抓取性评级：**需登录 Cookie**。
入口 URL：https://s.taobao.com/search?q=<kw>&s=<offset>
空结果常见原因：淘宝搜索与商品详情均为 JS 渲染 + 强反爬（滑块验证码、登录态校验），
未配置有效 PC_COOKIE_TAOBAO 时静态抓取基本无法拿到 g_page_config / auctions 商品数据。

本类给出真实的请求构造与内嵌 JSON（raw_title/view_price/detail_url/pic_url）解析骨架；
建议生产环境使用 Playwright/官方开放平台。失败回退示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_TAOBAO="th_sessionid=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://s.taobao.com/search?q={kw}&s={offset}"

# 淘宝搜索页内嵌 JSON（g_page_config / auctions）中的字段
_TITLE_RE = re.compile(r'"raw_title"\s*:\s*"(.*?)"')
_PRICE_RE = re.compile(r'"view_price"\s*:\s*"([\d.]+)"')
_SALES_RE = re.compile(r'"comment_count"\s*:\s*"([\d.]+)"')
_SHOP_RE = re.compile(r'"shop_name"\s*:\s*"(.*?)"')
_URL_RE = re.compile(r'"detail_url"\s*:\s*"(.*?)"')
_IMG_RE = re.compile(r'"pic_url"\s*:\s*"([^"]+)"')


class TaobaoSource(BaseSource):
    platform = "taobao"
    platform_name = "淘宝"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_TAOBAO") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        offset = (page - 1) * page_size
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), offset=offset)
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
        max_len = max(len(titles), len(prices))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
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
                    platform="taobao",
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
