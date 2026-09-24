# -*- coding: utf-8 -*-
"""苏宁易购数据源（真实抓取骨架）。

可抓取性评级：**需登录 Cookie**。
入口 URL：https://search.suning.com/<kw>/
空结果常见原因：苏宁 PC 搜索页虽返回 200 且体积较大（约 200KB），但商品列表
与成交价格由前端异步接口（带签名/登录态）返回，静态 HTML 中 price 多为筛选 UI
元素，未配置有效 PC_COOKIE_SUNING 时商品列表基本为空。

本类提供真实请求构造与 HTML 卡片 / 内嵌 JSON（commodityName/salePrice/itemUrl/
prodImg/sellCount）解析骨架；生产环境建议配登录 Cookie 或 Playwright 渲染。
异常吞掉返回空列表，由流水线回退示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_SUNING="userKey=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://search.suning.com/{kw}/&iy={offset}"

# 苏宁搜索结果：HTML 卡片 class 与内嵌 JSON 两种形态都尝试
_NAME_RE = re.compile(r'(?:class="sell-point"|commodityName)"?[^>]*>\s*([^<>{"]{4,80})')
_TITLE_JSON_RE = re.compile(r'"(?:commodityName|title|productName)"\s*:\s*"([^"]{2,120})"')
_PRICE_RE = re.compile(r'(?:class="price"[^>]*>¥?\s*([\d.]+)|"(?:salePrice|price)"\s*:\s*"?([\d.]+)"?)')
_CODE_RE = re.compile(r'(?://product\.suning\.com/(\d+)\.html|"commodityCode"\s*:\s*"?(\d{6,})"?|"itemUrl"[^"]*?/(\d+)\.html)')
_IMG_RE = re.compile(r'(?:src="(//img[\d.-]*\.cn[^"]+?\.(?:jpg|png|webp))"|"prodImg"\s*:\s*"(//[^"]+?)")')
_SALES_RE = re.compile(r'"(?:sellCount"|\bmonthSell\b)\s*:\s*"?(\d+(?:\.\d+)?)\s*(万)?"?')
_SHOP_RE = re.compile(r'"(?:shopName|sellerName)"\s*:\s*"([^"]{2,60})"')


class SuningSource(BaseSource):
    platform = "suning"
    platform_name = "苏宁易购"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_SUNING") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        offset = (page - 1) * page_size
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), offset=offset)
        headers = {"Referer": "https://www.suning.com/"}
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
        # 价格：合并两个捕获组
        price_raw = _PRICE_RE.findall(html)
        prices = [a or b for (a, b) in price_raw]
        names = _TITLE_JSON_RE.findall(html) or _NAME_RE.findall(html)
        # 商品码：合并三个捕获组
        code_raw = _CODE_RE.findall(html)
        codes = [a or b or c for (a, b, c) in code_raw]
        img_raw = _IMG_RE.findall(html)
        imgs = [a or b for (a, b) in img_raw]
        sales = _SALES_RE.findall(html)
        shops = _SHOP_RE.findall(html)
        max_len = max(len(names), len(prices), len(codes))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                code = codes[i] if i < len(codes) else ""
                url = f"https://product.suning.com/{code}.html" if code else ""
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                name = _strip_tags(names[i]) if i < len(names) else keyword
                shop = shops[i] if i < len(shops) else ""
                sale_val = _http.parse_sales(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="suning",
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


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()
