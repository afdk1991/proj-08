# -*- coding: utf-8 -*-
"""演示网页后端。

纯标准库实现，零第三方依赖，可直接运行：
    python server.py
然后浏览器访问 http://127.0.0.1:8000

提供两个能力：
1. 静态文件服务（web/ 目录下的前端页面）
2. JSON API：/api/search 现场运行采集流水线并返回结果
"""
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass

from price_collector import pipeline
from price_collector.sources import registry as _reg

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(ROOT, "web")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_KEYWORD = "蓝牙耳机"

# 允许访问的静态资源白名单（防目录穿越）
STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/style.css": "style.css",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 精简日志
        sys.stderr.write("[%s] %s\n" % (self.address_string(), fmt % args))

    # ---- 响应工具 ----
    def _send(self, code, body: bytes, ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _send_file(self, path):
        full = os.path.join(WEB_DIR, path)
        if not os.path.isfile(full):
            self._send_json(404, {"error": "not found"})
            return
        ext = os.path.splitext(path)[1].lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    # ---- 路由 ----
    def do_OPTIONS(self):
        """CORS 预检：允许指向外部后端的前端跨域 GET /api/*。"""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/api/"):
            self._handle_api(path, query)
            return

        target = STATIC_FILES.get(path)
        if target:
            self._send_file(target)
        else:
            self._send_json(404, {"error": "not found", "path": path})

    def _handle_api(self, path, query):
        if path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return

        if path == "/api/platforms":
            # 供前端动态拉取平台清单，避免前后端两份硬编码
            self._send_json(200, {
                "platforms": [
                    {"key": k, "name": _reg.PLATFORM_NAMES.get(k, k)}
                    for k in _reg.ALL_PLATFORMS
                ]
            })
            return

        if path == "/api/search":
            self._handle_search(query)
            return

        if path == "/api/demo":
            # 返回初始化用的示例数据（以默认关键词现场生成）
            self._handle_search({"keyword": [DEFAULT_KEYWORD]})
            return

        self._send_json(404, {"error": "unknown api", "path": path})

    def _handle_search(self, query):
        keyword = (query.get("keyword") or [DEFAULT_KEYWORD])[0].strip()
        if not keyword:
            self._send_json(400, {"error": "keyword 不能为空"})
            return

        valid_platforms = set(_reg.ALL_PLATFORMS)
        platforms = query.get("platforms")
        if platforms:
            platforms = [p for p in platforms[0].split(",") if p in valid_platforms]
            if not platforms:
                platforms = None

        # 唯一真实路径为 live；忽略历史 mock/auto 取值，全部按真实抓取处理
        source = (query.get("source") or ["live"])[0]

        try:
            page = max(1, int((query.get("page") or ["1"])[0]))
        except ValueError:
            page = 1
        try:
            size = max(5, int((query.get("size") or ["20"])[0]))
        except ValueError:
            size = 20

        try:
            result = pipeline.run(
                keyword=keyword,
                platforms=platforms,
                source_mode=source,
                page=page,
                page_size=size,
            )
            self._send_json(200, result.to_dict())
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": str(exc), "keyword": keyword})


def main():
    import argparse
    parser = argparse.ArgumentParser(description="比价探针本地/托管后端")
    parser.add_argument("--host", default=os.environ.get("HOST", DEFAULT_HOST),
                        help="监听地址（托管平台需 0.0.0.0）")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PORT", DEFAULT_PORT)), help="监听端口")
    args = parser.parse_args()

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"服务已启动: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止服务")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()