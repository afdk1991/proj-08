# -*- coding: utf-8 -*-
"""小红书数据源（真实抓取骨架）。

可抓取性评级：**需登录 Cookie**。
入口 URL：https://www.xiaohongshu.com/search_result?keyword=<kw>
空结果常见原因：小红书搜索登录墙极强，未登录或未配置有效 PC_COOKIE_XIAOHONGSHU
时返回登录/风控页（约 60KB 壳），笔记/商品列表（noteId/title/cover/price）
走加密接口，静态抓取基本为空。

本类提供真实请求构造与内嵌 JSON 字段解析骨架；生产环境建议配登录 Cookie
或 Playwright 渲染。异常吞掉返回空列表，由流水线回退示例数据。

通过环境变量启用真实抓取：
  PC_COOKIE_XIAOHONGSHU="web_session=...; webId=...; a1=...; ..."  PC_TIMEOUT=10  python cli.py search 关键词 --source live
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http
from ..models import Product

_SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={kw}&page={page}&source=web_explore_feed"

# 小红书搜索结果内嵌 JSON（__INITIAL_STATE__）字段
_TITLE_RE = re.compile(r'"(?:title|displayTitle|noteTitle)"\s*:\s*"([^"]{2,120})"')
_PRICE_RE = re.compile(r'"(?:price|salePrice)"\s*:\s*"?([\d.]+)"?')
_NOTE_RE = re.compile(r'"(?:noteId|note_id|id)"\s*:\s*"?([0-9a-f]{16,})"?')
_IMG_RE = re.compile(r'"(?:url|cover|image)"\s*:\s*"(https?://[^"]+?\.(?:jpg|jpeg|png|webp))"')
_USER_RE = re.compile(r'"(?:nickname|authorName)"\s*:\s*"([^"]{2,40})"')
_SALES_RE = re.compile(r'"(?:likedCount|liked_count|interactCount)"\s*:\s*"?(\d+(?:\.\d+)?)\s*(万)?"?')


class XiaohongshuSource(BaseSource):
    platform = "xiaohongshu"
    platform_name = "小红书"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_XIAOHONGSHU") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=page)
        headers = {"Referer": "https://www.xiaohongshu.com/"}
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
        notes = _NOTE_RE.findall(html)
        imgs = _IMG_RE.findall(html)
        users = _USER_RE.findall(html)
        sales = _SALES_RE.findall(html)
        max_len = max(len(titles), len(prices), len(notes))
        for i in range(max_len):
            try:
                if i >= len(prices):
                    break
                p = _http.parse_price(prices[i])
                if p <= 0:
                    continue
                nid = notes[i] if i < len(notes) else ""
                url = f"https://www.xiaohongshu.com/explore/{nid}" if nid else ""
                img = imgs[i] if i < len(imgs) else ""
                name = _unescape(titles[i]) if i < len(titles) else keyword
                user = _unescape(users[i]) if i < len(users) else ""
                sale_val = _http.parse_sales(sales[i]) if i < len(sales) else 0
                result.append(Product(
                    platform="xiaohongshu",
                    name=name,
                    price=p,
                    original_price=0.0,
                    sales=sale_val,
                    sales_text=sales[i] if i < len(sales) else "",
                    shop_rating=-1.0,
                    shop_name=user,
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
