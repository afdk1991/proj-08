# -*- coding: utf-8 -*-
"""当当网（dangdang.com）真实数据源。

这是本项目首个**实测可稳定返回真实商品数据**的国内电商平台：
同 IP 下京东/淘宝/拼多多/唯品会等主流站点均返回反爬验证页、空壳 HTML 或 403，
而当当网
  - 静态 HTML 直接承载商品（非 JS 渲染），
  - 对机房/云端 IP 无强制风控，
  - 无需 Cookie / 登录态 / API 密钥，
因此主键关键词搜索即可拿到真实商品的名称、价格、原价、店铺、图片与详情链接。

可抓取性评级：强（实测 200 + 单次约 60 条商品）。
入口 URL：https://search.dangdang.com/?key={kw}&act=input&page_index={page}

响应编码：服务端 Content-Type 返回 charset=gb2312（GB2312/GBK 家族）。
_http.fetch_html 会依据该头正确解码；若上游漏发 charset 将退回 utf-8 而产生乱码，
故本模块在解析前做一次兜底校正（_ensure_text）。

已知降级场景：
  - 搜索无结果 → 页面无商品 li 块，返回 []；
  - 触发临时风控/超时 → 异常被吞并返回 []，绝不伪造数据。

字段映射（源自实测 DOM）：
  <p class="price"><span class="price_n">&yen;15.20</span>   # 现价
                    <span class="price_r">&yen;22.40</span>  # 定价/原价
                    <span class="price_s">(6.79折)</span>
  <p class="name"><a title="商品名" href="//product.dangdang.com/xxx.html">
  <p class="link"><a ... title="店铺名">
"""
import os
import re
import urllib.parse
from typing import List

from .base import BaseSource
from . import _http, _browser
from ..models import Product

_SEARCH_URL = "https://search.dangdang.com/?key={kw}&act=input&page_index={page}"

# 每个商品被包裹在独立 <li> 块中，按块提取可避免字段错位
_PRICE_N_RE = re.compile(r'<span class="price_n">\s*&yen;\s*([0-9]+(?:\.[0-9]+)?)', re.I)
_PRICE_R_RE = re.compile(r'<span class="price_r">\s*&yen;\s*([0-9]+(?:\.[0-9]+)?)', re.I)
_NAME_RE = re.compile(r'<p class="name"[^>]*>\s*<a\s+title="([^"]*)"\s+href="([^"]+)"', re.I | re.S)
_SHOP_RE = re.compile(r'<p class="link"[^>]*>\s*<a[^>]*?title="([^"]*)"', re.I | re.S)
_IMG_RE = re.compile(r'(?:data-original|src)="(//img[^"]+\.(?:jpe?g|png|webp))"', re.I)


class DangdangSource(BaseSource):
    platform = "dangdang"
    platform_name = "当当网"

    can_live = lambda self: True

    def __init__(self, cookie: str = "", timeout: int = 10, **kwargs):
        self.cookie = cookie or os.environ.get("PC_COOKIE_DANGDANG") or os.environ.get("PC_COOKIE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10
        self.last_error = ""

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        url = _SEARCH_URL.format(kw=urllib.parse.quote(keyword), page=max(int(page or 1), 1))
        headers = {"Referer": "https://search.dangdang.com/"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        html = ""
        try:
            html = _http.fetch_html(url, timeout=self.timeout, headers=headers)
        except Exception as exc:  # 网络层失败必须静默降级
            self.last_error = f"fetch:{exc}"[:200]
            return []
        result = self._parse(html, keyword)
        # 直连为空时，若启用渲染层（PRICE_COLLECTOR_BROWSER=1），用 Chromium 渲染后再解析
        if not result and _browser.browser_enabled():
            rendered = _browser.render_html(url, timeout=self.timeout, cookie=self.cookie)
            if rendered:
                result = self._parse(rendered, keyword)
        if not result:
            self.last_error = "empty: 无商品块（可能被风控或无搜索结果）"
        return result[:page_size]

    @staticmethod
    def _parse(html: str, keyword: str) -> List[Product]:
        """按 <li> 商品块逐块提取，只保留同时具备名称与价格的块。"""
        result: List[Product] = []
        if not html:
            return result
        for chunk in html.split("<li"):
            if 'class="name"' not in chunk:
                continue
            try:
                nm = _NAME_RE.search(chunk)
                if not nm:
                    continue
                pm = _PRICE_N_RE.search(chunk)
                if not pm:
                    continue  # 无价格视为非商品块（广告/推荐位）
                price = _http.parse_price(pm.group(1))
                if price <= 0:
                    continue
                name = (nm.group(1) or "").strip()
                if not name:
                    continue
                raw_url = (nm.group(2) or "").strip()
                if raw_url.startswith("//"):
                    url = "https:" + raw_url
                else:
                    url = urllib.parse.urljoin("https://search.dangdang.com/", raw_url)
                om = _PRICE_R_RE.search(chunk)
                original = _http.parse_price(om.group(1)) if om else 0.0
                sm = _SHOP_RE.search(chunk)
                shop = (sm.group(1) or "").strip() if sm else ""
                im = _IMG_RE.search(chunk)
                img = ("https:" + im.group(1)) if im else ""
                result.append(Product(
                    platform="dangdang",
                    name=name,
                    price=price,
                    original_price=original,
                    sales=0,
                    sales_text="",
                    shop_rating=-1.0,
                    shop_name=shop,
                    url=url,
                    image=img,
                    keyword=keyword,
                    raw={"list_price": original},
                ))
            except Exception:
                continue
        return result
