# -*- coding: utf-8 -*-
"""TikTok Shop（字节跳动）数据源。

可抓取性评级：需登录 Cookie（强反爬/需登录可能性高）。
入口 URL：https://shop.tiktok.com/view/search?keyword={kw}
空结果常见原因：
  - 该搜索页为强 JS 渲染 + 风控（验证码/滑块），未登录或未通过风控时，
    静态抓取常直接超时、跳转登录页或返回风控页，HTML 中不含商品列表；
  - 即使配置 PC_COOKIE_TIKTOKSHOP，未命中有效风控 Cookie 时仍可能为空。
本类提供真实请求构造 + 内嵌 JSON 尽力解析骨架；抓不到即返回空列表，
绝不外抛、不伪造数据。海外站价格以美元计，price 填页面原价数值。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://shop.tiktok.com/view/search?keyword={kw}&page={page}"

# 商品卡片内嵌 JSON 字段（随前端结构变化需同步更新）
_TITLE_RE = re.compile(r'"title"\s*:\s*"([^"]+)"')
_PRICE_RE = re.compile(r'"(?:price|salePrice|formatted_price)"\s*:\s*"\$?\s*([\d.,]+)"')
_ORIG_RE = re.compile(r'"(?:originalPrice|compareAtPrice|listPrice)"\s*:\s*"\$?\s*([\d.,]+)"')
_URL_RE = re.compile(r'"(?:productUrl|url|detailUrl)"\s*:\s*"(https?[^"]*?/product/[^"]+)"')
_IMG_RE = re.compile(r'"(?:image|img|cover|mainImage)"\s*:\s*"(https?[^"]+\.(?:jpe?g|png|webp)[^"]*)"')


class TiktokshopSource(BaseSource):
    platform = "tiktokshop"
    platform_name = "TikTok Shop"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_TIKTOKSHOP") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page)
        headers = {"Referer": "https://shop.tiktok.com/"}
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
        max_len = max(len(titles), len(prices))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                url = urls[i] if i < len(urls) else ""
                img = imgs[i] if i < len(imgs) else ""
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = _unescape(titles[i]) if i < len(titles) else keyword
                result.append(Product(
                    platform="tiktokshop",
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


def _unescape(s: str) -> str:
    return (s or "").replace("\\u003c", "<").replace("\\/", "/").replace("\\\"", "\"").strip()
