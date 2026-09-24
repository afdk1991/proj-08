# -*- coding: utf-8 -*-
"""Amazon 亚马逊（Amazon.com）数据源。

可抓取性评级：强反爬可能空结果。
入口 URL：https://www.amazon.com/s?k={kw}
空结果常见原因：
  - Amazon 反爬极强，本机直连静态抓取常返回 HTTP 503 / 验证码页
    （“Enter the characters you see below”），此时 HTML 不含商品；
  - 偶发放行时，结果页每个商品以 data-asin 区块承载，价格在
    <span class="a-offscreen"> 内、链接 /dp/<ASIN>、主图 m.media-amazon.com，
    本类按区块逐块提取字段。
本类仅做公开网页静态抓取 + 标准 UA，不做验证码破解/代理池；抓不到即返回
空列表，绝不外抛、不伪造数据。海外站价格以美元计，price 填页面原价数值。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http, _browser
from ..models import Product

_SEARCH_URL = "https://www.amazon.com/s?k={kw}&page={page}"

# 按商品区块 data-asin 切分后，在每块内提取字段
_BLOCK_RE = re.compile(r'data-asin="([A-Z0-9]{10})"')
_PRICE_RE = re.compile(r'class="a-offscreen">\$?\s*([\d.,]+)')
_ORIG_RE = re.compile(r'class="a-price-a10n[^"]*"[^>]*>.*?\$?\s*([\d.,]+)', re.S)
_TITLE_RE = re.compile(r'<h2[^>]*>.*?<span[^>]*>([^<]+)</span>', re.S)
_LINK_RE = re.compile(r'href="(/dp/[A-Z0-9]{10}[^"]*)"')
_IMG_RE = re.compile(r'src="(https://m\.media-amazon\.com/images/[^"]+\.(?:jpe?g|png|webp)[^"]*)"')


class AmazonSource(BaseSource):
    platform = "amazon"
    platform_name = "Amazon 亚马逊"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_AMAZON") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page)
        headers = {
            "Referer": "https://www.amazon.com/",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        try:
            html = _http.fetch_html(url, timeout=self.timeout, headers=headers)
        except Exception:
            html = ""
        result = self._parse(html, keyword)
        # 直连为空时，若启用渲染层（PRICE_COLLECTOR_BROWSER=1），用 Chromium 渲染后再解析
        if not result and _browser.browser_enabled():
            rendered = _browser.render_html(url, timeout=self.timeout, cookie=self.cookie)
            if rendered:
                result = self._parse(rendered, keyword)
        return result[:page_size]

    @staticmethod
    def _parse(html: str, keyword: str) -> List[Product]:
        result: List[Product] = []
        # 用 data-asin 出现位置把 HTML 切成逐商品块，避免价格/标题错位
        starts = [m.start() for m in _BLOCK_RE.finditer(html)]
        starts.append(len(html))
        for i in range(len(starts) - 1):
            try:
                block = html[starts[i]:starts[i + 1]]
                pm = _PRICE_RE.search(block)
                if not pm:
                    continue
                p = _http.parse_price(pm.group(1))
                if p <= 0:
                    continue
                tm = _TITLE_RE.search(block)
                lm = _LINK_RE.search(block)
                im = _IMG_RE.search(block)
                om = _ORIG_RE.search(block)
                name = tm.group(1).strip() if tm else keyword
                url = ("https://www.amazon.com" + lm.group(1)) if lm else ""
                img = im.group(1) if im else ""
                original = _http.parse_price(om.group(1)) if om else 0.0
                result.append(Product(
                    platform="amazon",
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
