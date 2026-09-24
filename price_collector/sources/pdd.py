# -*- coding: utf-8 -*-
"""拼多多数据源（真实抓取骨架）。

可抓取性评级：**仅 App**。
入口 URL：https://mobile.yangkeduo.com/search_result.html?search_key=<kw>
空结果常见原因：拼多多主要面向 App/移动端，PC 搜索需登录态且存在较强风控
（验证码/设备指纹），静态抓取 mobile 页面基本为空。

本类给出真实请求构造与移动端内嵌 JSON（goods_name/price/goods_id/hd_thumb_url/sales_num）
解析骨架；生产环境建议使用 App 抓包接口或浏览器渲染方案。失败回退示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_PDD="PDD_SESSION=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://mobile.yangkeduo.com/search_result.html?search_key={kw}"

# 移动端搜索页内嵌 JSON 中的字段（goods_name / price / goods_id / thumb_url）
_NAME_RE = re.compile(r'"goods_name"\s*:\s*"(.*?)"')
_PRICE_RE = re.compile(r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?')
_ID_RE = re.compile(r'"goods_id"\s*:\s*"?(\d+)"?')
_IMG_RE = re.compile(r'"hd_thumb_url"\s*:\s*"(.*?)"')
_SALES_RE = re.compile(r'"sales_num"\s*:\s*"?(\d+)"?')


class PddSource(BaseSource):
    platform = "pdd"
    platform_name = "拼多多"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_PDD") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword))
        headers = {"Referer": "https://mobile.yangkeduo.com/"}
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
        ids = _ID_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        sales = _SALES_RE.findall(html)
        max_len = max(len(names), len(prices), len(ids))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                gid = ids[i] if i < len(ids) else ""
                url = f"https://mobile.yangkeduo.com/goods.html?goods_id={gid}" if gid else ""
                img = imgs[i] if i < len(imgs) else ""
                if img and img.startswith("//"):
                    img = "https:" + img
                name = _unescape(names[i]) if i < len(names) else keyword
                sale_val = int(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="pdd",
                    name=name,
                    price=p,
                    original_price=0.0,
                    sales=sale_val,
                    sales_text=f"{sale_val}+" if sale_val else "",
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
