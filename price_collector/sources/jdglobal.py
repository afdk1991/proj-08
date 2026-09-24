# -*- coding: utf-8 -*-
"""京东国际（JD.hk / 京东集团）数据源（真实抓取骨架）。

可抓取性评级：强反爬可能空结果
入口 URL：https://search.jd.com/Search?keyword={关键词}&enc=utf-8&ist=jhs
说明：京东国际（京东全球购/海外购）首页 www.jd.hk 可静态访问（200），但其
搜索结果复用 search.jd.com 主站搜索接口，未携带登录态/风控通过时直接返回
「京东验证」滑块页（实测 title=京东验证，正文仅 ~2.7KB 无商品）。本类沿用
京东主站搜索页内嵌字段解析正则；空结果常见原因：触发京东风控验证、需要
登录 Cookie（PC_COOKIE_JDGLOBAL）或代理/浏览器渲染。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://search.jd.com/Search?keyword={kw}&enc=utf-8&ist=jhs&page={page}"

# 京东搜索页商品卡片尽力解析正则（随页面结构变化需同步更新）
_PRICE_RE = re.compile(r'<i>([\d.]+)</i>')
_NAME_RE = re.compile(r'<em>(.*?)</em>', re.S)
_ORIG_RE = re.compile(r'<del[^>]*>¥?\s*([\d.]+)')
_URL_RE = re.compile(r'href="(//item\.jd\.com/(\d+)\.html)"')
_IMG_RE = re.compile(r'data-lazy-img="(//img\d+\.360buyimg\.com/[^"]+)"')


class JdglobalSource(BaseSource):
    platform = "jdglobal"
    platform_name = "京东国际"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (cookie or os.environ.get("PC_COOKIE_JDGLOBAL")
                       or os.environ.get("PC_COOKIE", ""))
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=str(page * 2 - 1))
        headers = {"Referer": "https://www.jd.hk/"}
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
        prices = _PRICE_RE.findall(html)
        names = _NAME_RE.findall(html)
        origs = _ORIG_RE.findall(html)
        urls = _URL_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        for i, price in enumerate(prices[:50]):
            try:
                p = _http.parse_price(price)
                if p <= 0:
                    continue
                url = ("https:" + urls[i][0]) if i < len(urls) else ""
                img = ("https:" + imgs[i]) if i < len(imgs) else ""
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = _strip_tags(names[i]) if i < len(names) else keyword
                result.append(Product(
                    platform="jdglobal",
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
