# -*- coding: utf-8 -*-
"""转转（转转集团）数据源（真实抓取骨架）。

可抓取性评级：仅 App
入口 URL：https://www.zhuanzhuan.com/search?kw={kw}
空结果常见原因：
  - 转转 PC 官网 www.zhuanzhuan.com 仅约 2.3KB，是 App 下载/品牌落地页；
    /search、/list、/search.html 等路径实测均返回 404，PC 端无独立商品搜索。
  - 商品搜索、验机报告、下单均在转转 App / 找靓机 App 内完成，Web 端不开放。
  - 本类保留标称搜索 URL 作为骨架，请求被 404/重定向时吞异常返回 []，属预期。

生产建议：抓 App 接口（需登录态 + 签名）或改用 App 抓包方案。抓取失败一律返回空列表。
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.zhuanzhuan.com/search?kw={kw}"

# 转转商品卡片内联 JSON 的尽力解析正则
_NAME_RE = re.compile(r'"(?:title|name|goodsName|spuName)"\s*:\s*"([^"]+)"')
_PRICE_RE = re.compile(r'"(?:price|salePrice|currentPrice|zzPrice)"\s*:\s*"?([\d.]+)')
_ORIG_RE = re.compile(r'"(?:originPrice|originalPrice|marketPrice)"\s*:\s*"?([\d.]+)')
_SHOP_RE = re.compile(r'"(?:shopName|userName|sellerName)"\s*:\s*"([^"]+)"')
_IMG_RE = re.compile(r'"(?:img|image|picUrl|imgUrl)"\s*:\s*"(//[^"]+?)"')
_URL_RE = re.compile(r'"(?:productId|itemId|zzId)"\s*:\s*"?(\d+)"')


class ZhuanzhuanSource(BaseSource):
    platform = "zhuanzhuan"
    platform_name = "转转"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = (
            cookie
            or os.environ.get("PC_COOKIE_ZHUANZHUAN")
            or os.environ.get("PC_COOKIE", "")
        )
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {"Referer": "https://www.zhuanzhuan.com/"}
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
        names = _NAME_RE.findall(html)
        prices = _PRICE_RE.findall(html)
        origs = _ORIG_RE.findall(html)
        shops = _SHOP_RE.findall(html)
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
                    url = "https://www.zhuanzhuan.com/detail/" + str(ids[i])
                name = _strip_tags(names[i]) if i < len(names) else keyword
                shop = _strip_tags(shops[i]) if i < len(shops) else ""
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                result.append(Product(
                    platform="zhuanzhuan",
                    name=name,
                    price=p,
                    original_price=original,
                    sales=0,
                    sales_text="",
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
