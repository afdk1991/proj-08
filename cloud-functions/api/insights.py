# -*- coding: utf-8 -*-
"""AI 比价洞察 API：GET /api/insights?keyword=...&platforms=...

流程：跑一次真实采集 pipeline -> 用 price_collector.ai 生成大模型比价洞察。
独立于 /api/search，前端在用户点击「AI 智能分析」时才调用，避免每次搜索
都产生模型调用。未配置 AI 密钥 / 无数据时返回 enabled=false，绝不崩溃。
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
_FUNCS = os.path.dirname(_HERE)
_PROJECT = os.path.dirname(_FUNCS)
for _p in (_FUNCS, _PROJECT):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

PIPELINE = None
AI = None
ANALYSIS = None
IMPORT_ERROR = ""
try:
    from price_collector import pipeline as PIPELINE  # noqa: E402
    from price_collector import ai as AI  # noqa: E402
    from price_collector import analysis as ANALYSIS  # noqa: E402
except Exception as _e:
    IMPORT_ERROR = repr(_e)

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
    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        if PIPELINE is None or AI is None:
            _send_json(self, {"enabled": False, "reason": "import_failed",
                              "detail": IMPORT_ERROR}, status=500)
            return

        q = parse_qs(urlparse(self.path).query)
        get = lambda k, d=None: q.get(k, [d])[0]
        keyword = (get("keyword", "") or "").strip()
        if not keyword:
            _send_json(self, {"enabled": False, "reason": "no_keyword",
                              "message": "缺少 keyword 参数"})
            return

        from price_collector.sources.registry import ALL_PLATFORMS as _ALL
        platforms = [p for p in (get("platforms", "") or "").split(",") if p] or list(_ALL)
        try:
            size = min(50, max(1, int(get("size", "30"))))
        except ValueError:
            size = 30

        try:
            result = PIPELINE.run(
                keyword=keyword, platforms=platforms,
                source_mode="live", page_size=size)
            summary = ANALYSIS.summarize(result.sorted_products)
            insights = AI.ai_insights(
                keyword=keyword,
                products=result.sorted_products,
                platform_stats=result.platform_stats,
                summary=summary,
            )
            # 附带基础统计，便于前端展示上下文
            insights["keyword"] = keyword
            insights["total"] = result.total
            insights["summary"] = summary
            _send_json(self, insights)
        except Exception as e:
            _send_json(self, {"enabled": False, "reason": "pipeline_failed",
                              "message": str(e)}, status=500)
