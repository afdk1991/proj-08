# -*- coding: utf-8 -*-
"""AI 智能层（可选增强，纯标准库实现）。

能力：
- ai_insights：基于真实采集结果，用大模型生成比价洞察（一句话结论 / 最划算
  推荐 / 价格区间解读 / 平台差异 / 避坑建议），结构化 JSON 返回。

合规与稳健（与 _browser.py / _cps 同一设计哲学）：
- 仅把**已采集到的真实商品数据**喂给模型，要求"只基于数据、不编造价格"；
- 兼容 OpenAI Chat Completions 协议 —— 默认可接火山引擎方舟（Ark），
  也可通过环境变量指向任意 OpenAI 兼容端点；
- 无 API Key / 未配置 / 网络失败 / 返回非法 —— 一律返回 {"enabled": False}
  并带 reason，绝不崩溃、绝不伪造洞察。

配置（环境变量优先，回退构建时写入的 _ai_config 模块）：
- PC_AI_API_KEY / ARK_API_KEY / OPENAI_API_KEY   密钥
- PC_AI_BASE_URL / ARK_BASE_URL / OPENAI_BASE_URL 端点（默认方舟）
- PC_AI_MODEL / ARK_MODEL / OPENAI_MODEL          模型/推理接入点
"""
import json
import os
import re
import urllib.request
from typing import List, Dict, Any, Optional

from .models import Product

_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_DEFAULT_MODEL = "doubao-seed-1-6-flash-250828"
_TIMEOUT = 30
_MAX_PRODUCTS_IN_PROMPT = 40

_SYSTEM_PROMPT = (
    "你是一名严谨的电商比价分析师。用户会给出多个平台搜索同一关键词得到的"
    "真实商品数据（名称、现价、原价、平台）。请只基于这些数据进行分析，"
    "不得编造数据中不存在的价格、平台或商品；若数据不足请明确指出。"
    "语言简洁、客观、对普通消费者友好。必须只输出一个 JSON 对象，不要输出"
    "任何解释文字或 markdown 代码块。"
)


# ---------------------------------------------------------------- 配置读取
def _config() -> Dict[str, str]:
    api_key = (
        os.environ.get("PC_AI_API_KEY")
        or os.environ.get("ARK_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )
    base_url = (
        os.environ.get("PC_AI_BASE_URL")
        or os.environ.get("ARK_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or _DEFAULT_BASE_URL
    )
    model = (
        os.environ.get("PC_AI_MODEL")
        or os.environ.get("ARK_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or _DEFAULT_MODEL
    )
    # 回退到构建时写入的本地配置（gitignored）
    if not api_key:
        try:
            from . import _ai_config  # type: ignore
            api_key = api_key or getattr(_ai_config, "AI_API_KEY", "")
            base_url = getattr(_ai_config, "AI_BASE_URL", base_url) or base_url
            model = getattr(_ai_config, "AI_MODEL", model) or model
        except Exception:
            pass
    return {"api_key": (api_key or "").strip(),
            "base_url": (base_url or _DEFAULT_BASE_URL).rstrip("/"),
            "model": (model or _DEFAULT_MODEL).strip()}


def ai_available() -> bool:
    return bool(_config()["api_key"])


# ---------------------------------------------------------------- 数据组装
def _build_user_message(keyword: str, products: List[Product],
                        platform_stats: List[Any], summary: Dict[str, Any]) -> str:
    # 平台中文名
    try:
        from .sources.registry import PLATFORM_NAMES
    except Exception:
        PLATFORM_NAMES = {}

    compact_products = []
    for p in products[:_MAX_PRODUCTS_IN_PROMPT]:
        compact_products.append({
            "name": p.name,
            "price": p.price,
            "original_price": p.original_price or None,
            "platform": PLATFORM_NAMES.get(p.platform, p.platform),
        })
    stats = []
    for st in platform_stats:
        d = st if isinstance(st, dict) else getattr(st, "__dict__", {})
        stats.append({
            "platform": PLATFORM_NAMES.get(d.get("platform"), d.get("platform")),
            "count": d.get("count"),
            "min": d.get("min_price"),
            "max": d.get("max_price"),
            "avg": d.get("avg_price"),
        })

    payload = {
        "keyword": keyword,
        "overall": summary,
        "platform_stats": stats,
        "products": compact_products,
        "输出要求": {
            "headline": "string，一句话总结本次比价的核心结论",
            "best_pick": {"name": "string，最值得买的商品名(须来自products)",
                          "reason": "string，推荐理由(价格/折扣/平台)"},
            "price_view": "string，价格区间与分布解读，1-2句",
            "platform_view": "string，各平台价格/数量差异，1-2句",
            "tips": ["string，避坑或购买建议，2-4条"],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------- 主入口
def ai_insights(keyword: str, products: List[Product],
                platform_stats: List[Any], summary: Dict[str, Any]) -> Dict[str, Any]:
    """生成 AI 比价洞察。任何不可用/失败都返回 {"enabled": False, "reason": ...}。"""
    cfg = _config()
    if not cfg["api_key"]:
        return {"enabled": False, "reason": "no_api_key",
                "message": "未配置 AI 密钥，配置 PC_AI_API_KEY 后启用"}
    if not products:
        return {"enabled": False, "reason": "no_products",
                "message": "当前没有可分析的真实商品数据"}

    body = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(
                keyword, products, platform_stats, summary)},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    url = cfg["base_url"] + "/chat/completions"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + cfg["api_key"],
    })

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:
        return {"enabled": False, "reason": "request_failed",
                "message": "AI 服务请求失败：" + str(e)[:120]}

    try:
        resp_json = json.loads(raw)
        content = resp_json["choices"][0]["message"]["content"]
    except Exception:
        return {"enabled": False, "reason": "bad_response",
                "message": "AI 返回格式异常"}

    parsed = _extract_json(content)
    if not parsed:
        return {"enabled": False, "reason": "bad_json",
                "message": "无法解析 AI 输出的 JSON"}

    parsed["enabled"] = True
    parsed["model"] = cfg["model"]
    return parsed


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """从模型输出中提取 JSON 对象（兼容被 ```json 包裹或前后带文字的情况）。"""
    if not text:
        return None
    text = text.strip()
    # 去掉 markdown 代码块
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    # 退而求其次：截取第一个 { 到最后一个 }
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None
