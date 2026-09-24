# -*- coding: utf-8 -*-
"""比价搜索 API：GET /api/search

把项目的采集流水线（price_collector）原样部署为 EdgeOne 云函数（Python 运行时）。
price_collector 作为辅助模块与函数一同位于 cloud-functions/ 下，会被构建器一并打包。

- 前端直接同域调用 /api/search，无需跨域
- 云端无外网/Cookie 时 live 模式自然返回空结果（total 0），绝不伪造数据
- 导入失败时依然注册路由并返回 500 + 错误详情，避免静默 404
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---------- 路径解析：让 price_collector 可被导入 ----------
# search.py 位于 <project>/cloud-functions/api/search.py
_HERE = os.path.dirname(os.path.abspath(__file__))        # .../cloud-functions/api
_FUNCS = os.path.dirname(_HERE)                            # .../cloud-functions
_PROJECT = os.path.dirname(_FUNCS)                         # <project>（可能不存在包）

for _p in (_FUNCS, _PROJECT):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

PIPELINE = None
IMPORT_ERROR = ""
try:
    from price_collector import pipeline as PIPELINE  # noqa: E402
except Exception as _e:  # 保留错误信息，路由仍需注册
    IMPORT_ERROR = repr(_e)

# 允许的来源（同域即可，这里放开便于调试）
CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _send_json(self, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    for k, v in CORS.items():
        self.send_header(k, v)
    self.end_headers()
    self.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def _parse(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        get = lambda k, d=None: q.get(k, [d])[0]
        keyword = (get("keyword", "") or "").strip()
        source = get("source", "live")
        # 唯一真实路径 live；历史 mock/auto 一律按真实抓取处理（云端无外网/Cookie 时自然返回空）
        from price_collector.sources.registry import ALL_PLATFORMS as _ALL
        platforms = [p for p in (get("platforms", "") or "").split(",") if p] or list(_ALL)
        try:
            page = max(1, int(get("page", "1")))
        except ValueError:
            page = 1
        try:
            size = min(200, max(1, int(get("size", "50"))))
        except ValueError:
            size = 50
        return keyword, source, platforms, page, size

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        if PIPELINE is None:
            _send_json(self, {
                "error": "price_collector import failed",
                "detail": IMPORT_ERROR,
                "sys_path": sys.path[:6],
                "funcs_dir": _FUNCS,
            }, status=500)
            return

        keyword, source, platforms, page, size = self._parse()
        try:
            result = PIPELINE.run(
                keyword=keyword,
                platforms=platforms,
                source_mode=source,
                page=page,
                page_size=size,
            )
            _send_json(self, result.to_dict())
        except Exception as e:  # 任何异常都不让函数崩溃，返回结构化错误
            _send_json(self, {
                "error": str(e),
                "keyword": keyword,
                "source_mode": source,
            }, status=500)
