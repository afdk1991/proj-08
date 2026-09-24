# -*- coding: utf-8 -*-
"""微信小店 / 视频号小店数据源（真实抓取骨架）。

可抓取性评级：**仅 App**。
入口 URL：https://channels.weixin.qq.com/search?keyWord=<kw>（PC 视频号助手）
空结果常见原因：微信小店 / 视频号小店为微信生态闭环，商品仅在微信 App /
视频号内可见，PC 端无公开网页搜索端点；channels.weixin.qq.com 为视频号助手
后台，需登录态且不开放商品列表搜索。标准库静态抓取基本为空。

本类提供真实请求构造与字段解析骨架（标题/价格/商品 ID/封面），仅作占位与
可插拔结构；生产环境建议 App 抓包或微信开放平台接口。异常吞掉返回空列表。

通过环境变量启用真实抓取：
  PC_COOKIE_WECHAT="wxtoken=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://channels.weixin.qq.com/search?keyWord={kw}&page={page}"

# 视频号小店商品内嵌 JSON 字段（商品卡片）
_TITLE_RE = re.compile(r'"(?:title|productTitle|name)"\s*:\s*"([^"]{2,120})"')
_PRICE_RE = re.compile(r'"(?:price|salePrice|sale_price)"\s*:\s*"?([\d.]+)"?')
_ORIG_RE = re.compile(r'"(?:originPrice|originalPrice)"\s*:\s*"?([\d.]+)"?')
_PID_RE = re.compile(r'"(?:productId|skuId|finderId)"\s*:\s*"?(\d{8,})"?')
_IMG_RE = re.compile(r'"(?:coverUrl|headImgUrl|imgUrl)"\s*:\s*"(https?://[^"]+?)"')
_SALES_RE = re.compile(r'"(?:sales|soldCount|saleCount)"\s*:\s*"?(\d+(?:\.\d+)?)\s*(万)?"?')


class WechatSource(BaseSource):
    platform = "wechat"
    platform_name = "微信小店·视频号小店"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_WECHAT") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page)
        headers = {"Referer": "https://channels.weixin.qq.com/"}
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
        pids = _PID_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        sales = _SALES_RE.findall(html)
        max_len = max(len(titles), len(prices), len(pids))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                pid = pids[i] if i < len(pids) else ""
                url = f"https://channels.weixin.qq.com/goods/{pid}" if pid else ""
                img = imgs[i] if i < len(imgs) else ""
                original = _http.parse_price(origs[i]) if i < len(origs) else 0.0
                name = _unescape(titles[i]) if i < len(titles) else keyword
                sale_val = _http.parse_sales(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="wechat",
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
