# -*- coding: utf-8 -*-
"""唯品会数据源（真实抓取骨架）。

可抓取性评级：**需浏览器自动化**。
入口 URL：https://category.vip.com/suggest.php?keyword=<kw>
空结果常见原因：唯品会搜索页为 JS 渲染（前端 SPA），静态 HTML 仅含骨架与
dns-prefetch 提示，商品列表（price/title/img/goodsId）由前端异步拉取后渲染，
标准库静态抓取基本为空。

本类提供真实请求构造与内嵌 JSON 字段解析骨架；生产环境建议 Playwright 渲染
或配 Cookie 调内部接口。异常吞掉返回空列表，由流水线回退示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_VIP="VIP_CLIENT_UID=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://category.vip.com/suggest.php?keyword={kw}&page={page}"

# 唯品会搜索结果内嵌 JSON / __INITIAL_STATE__ 中的字段
_TITLE_RE = re.compile(r'"title"\s*:\s*"([^"]{2,120})"')
_PRICE_RE = re.compile(r'"(?:price|vipPrice|salePrice)"\s*:\s*"?([\d.]+)"?')
_ORIG_RE = re.compile(r'"(?:marketPrice|originPrice)"\s*:\s*"?([\d.]+)"?')
_ID_RE = re.compile(r'"(?:goodsId|goods_sn|proId)"\s*:\s*"?(\d{6,})"?')
_IMG_RE = re.compile(r'"(?:img|image|listImage)"\s*:\s*"(//[^"]+?)"')
_SALES_RE = re.compile(r'"(?:sales|soldCount|sold)"\s*:\s*"?(\d+(?:\.\d+)?)\s*(万)?"?')


class VipSource(BaseSource):
    platform = "vip"
    platform_name = "唯品会"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_VIP") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page)
        headers = {"Referer": "https://www.vip.com/"}
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
        ids = _ID_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        sales = _SALES_RE.findall(html)
        max_len = max(len(titles), len(prices), len(ids))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                gid = ids[i] if i < len(ids) else ""
                url = f"https://detail.vip.com/detail-{gid}.html" if gid else ""
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = _unescape(titles[i]) if i < len(titles) else keyword
                sale_val = _http.parse_sales(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="vip",
                    name=name,
                    price=p,
                    original_price=original,
                    sales=sale_val,
                    sales_text=sales[i] if i < len(sales) else "",
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
