# -*- coding: utf-8 -*-
"""可选浏览器渲染层（Playwright，纯增强、非必需）。

合规边界：
- 仅用 Chromium 渲染**公开**搜索页、标准 UA；
- 不做验证码破解、不模拟点击、不维护代理池；
- 被拦截/需登录时优雅返回空串，由源复用现有解析正则或落到空结果。

设计原则（保持"零第三方依赖也能跑"）：
- playwright 未安装 / 未启用开关 / 任何异常 → 全部静默降级为 ""，
  调用方退回直连 HTTP 或空结果，绝不崩溃、绝不伪造。
- 开关：环境变量 PRICE_COLLECTOR_BROWSER=1 才启用渲染。
"""
import os
from typing import Optional

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def browser_enabled() -> bool:
    return os.environ.get("PRICE_COLLECTOR_BROWSER", "0") == "1"


def render_html(url: str, timeout: int = 25, cookie: str = "",
                wait_ms: int = 1500) -> str:
    """用 Playwright 渲染一个 URL，返回渲染后的完整 HTML。

    任何失败（未安装 playwright、超时、被拦截、启动失败）都返回 ""，
    调用方据此退回直连或空结果。cookie 为 "k=v; k2=v2" 形式，仅用于注入登录态。
    """
    if not browser_enabled():
        return ""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except Exception:
        return ""

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=[
                "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled",
            ])
            ctx = browser.new_context(user_agent=_DEFAULT_UA, locale="zh-CN")
            if cookie:
                from urllib.parse import urlparse
                host = urlparse(url).hostname or ""
                ctx.add_cookies(_parse_cookie(cookie, host))
            page = ctx.new_page()
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            try:
                page.wait_for_timeout(wait_ms)  # 等首屏异步商品渲染
            except Exception:
                pass
            return page.content()
    except Exception:
        return ""
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass


def _parse_cookie(cookie: str, host: str = "") -> list:
    cookies = []
    domain = "." + host.split(".", 1)[1] if host and host.count(".") >= 1 else host
    for pair in (cookie or "").split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            c = {"name": k.strip(), "value": v.strip(), "path": "/"}
            if domain:
                c["domain"] = domain
            cookies.append(c)
    return cookies
