# -*- coding: utf-8 -*-
"""出网自检端点：GET /api/netcheck

验证 EdgeOne 云函数运行时能否访问公网（决定 live 采集是否可能出数据）。
仅诊断用，不参与业务路径。
"""
import json
from http.server import BaseHTTPRequestHandler


def _send_json(self, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    self.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_GET(self):
        import urllib.request as _ur
        results = {}
        for host in ("https://example.com", "https://www.baidu.com"):
            try:
                with _ur.urlopen(host, timeout=8) as _r:
                    results[host] = {"ok": True, "status": _r.status, "bytes": len(_r.read(2048))}
            except Exception as _e:
                results[host] = {"ok": False, "error": repr(_e)[:200]}
        _send_json(self, {"netcheck": results})
