# -*- coding: utf-8 -*-
"""京东数据源（真实抓取骨架）。

可抓取性评级：**强反爬可能空结果**。
入口 URL：https://search.jd.com/Search?keyword=<kw>&enc=utf-8&page=<page>
空结果常见原因：京东搜索页为 JS 动态渲染 + 风控（滑块/登录态校验），静态抓取
通常只拿到壳 HTML，商品价格/列表需异步接口返回；未配置有效登录 Cookie 时基本为空。

本类提供真实的 HTTP 请求 + 正则解析骨架，作为「可插拔真实数据源」参照实现；
生产使用需配置登录 Cookie（PC_COOKIE_JD）/代理，或改用 Playwright 等浏览器渲染方案。
抓取失败返回空列表，由流水线回退到示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_JD="pin=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://search.jd.com/Search?keyword={kw}&enc=utf-8&page={page}"

# 价格 / 名称 / 原价 / 链接 / 主图 的尽力解析正则（随页面结构变化需同步更新）
_PRICE_RE = re.compile(r'<i>([\d.]+)</i>')
_NAME_RE = re.compile(r'<em>(.*?)</em>', re.S)
_ORIG_RE = re.compile(r'<del[^>]*>¥?\s*([\d.]+)')
_URL_RE = re.compile(r'href="(//item\.jd\.com/(\d+)\.html)"')
_IMG_RE = re.compile(r'data-lazy-img="(//img\d+\.360buyimg\.com/[^"]+)"')


class JDSource(BaseSource):
    platform = "jd"
    platform_name = "京东"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        # cookie/timeout 可由 __init__ 传入（pipeline 透传），也可读环境变量兜底
        self.cookie = cookie or os.environ.get("PC_COOKIE_JD") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=str(page * 2 - 1))
        headers = {}
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
                    platform="jd",
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
