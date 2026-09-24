# -*- coding: utf-8 -*-
"""闲鱼（goofish.com，原 2.taobao.com）数据源（真实抓取骨架）。

可抓取性评级：强反爬可能空结果
入口 URL：https://www.goofish.com/search?q={kw}
空结果常见原因：
  - 闲鱼网页搜索依赖阿里 baxia 风控（页面内联 window.__baxia__ 初始化脚本），
    真实搜索接口 /mtop.taobao.idlemtopsearch.pc.search/ 需要 baxia 签名参数
    （uab/umid/et），无浏览器环境无法生成。
  - 静态 HTML 仅约 11KB 壳，不含商品列表。
  - 即便配置 PC_COOKIE_XIANYU，缺少 baxia 签名时接口仍返回空/拦截，属预期。

生产建议：必须使用真实浏览器（Playwright）让 baxia 脚本生成签名后再取接口。
抓取失败一律返回空列表。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.goofish.com/search?q={kw}"

# 闲鱼商品卡片内联 JSON 的尽力解析正则
_TITLE_RE = re.compile(r'"(?:itemTitle|title|name)"\s*:\s*"([^"]+)"')
_PRICE_RE = re.compile(r'"(?:price|currentPrice|sellPrice)"\s*:\s*"?([\d.]+)')
_IMG_RE = re.compile(r'"(?:picUrl|img|image|pic)"\s*:\s*"(//[^"]+?)"')
_URL_RE = re.compile(r'"(?:itemId|id|itemNumId)"\s*:\s*"?(\d{8,})"')


class XianyuSource(BaseSource):
    platform = "xianyu"
    platform_name = "闲鱼"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (
            cookie
            or os.environ.get("PC_COOKIE_XIANYU")
            or os.environ.get("PC_COOKIE", "")
        )
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {"Referer": "https://www.goofish.com/"}
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
        imgs = _IMG_RE.findall(html)
        ids = _URL_RE.findall(html)
        for i, price in enumerate(prices[:50]):
            try:
                p = _http.parse_price(price)
                if p <= 0:
                    continue
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                url = ""
                if i < len(ids):
                    url = "https://www.goofish.com/item?id=" + str(ids[i])
                name = _unescape(titles[i]) if i < len(titles) else keyword
                result.append(Product(
                    platform="xianyu",
                    name=name,
                    price=p,
                    original_price=0.0,
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
