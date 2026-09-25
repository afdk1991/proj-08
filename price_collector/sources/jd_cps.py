# -*- coding: utf-8 -*-
"""京东联盟（京粉 CPS）官方 API 数据源。

正规采集途径：在 union.jd.com 注册京东联盟，新建应用拿到
AppKey / AppSecret，申请 jd.union.open.goods.query 权限，
通过官方接口按关键词查商品，返回 SKU 名称、价格、主图、推广链接。

凭据环境变量：
  PC_CPS_JD_APPKEY    京东联盟 AppKey
  PC_CPS_JD_SECRET    京东联盟 AppSecret

未配置时 can_live=False、fetch 返回 []。
"""
import os
import time
import hashlib
import urllib.parse
import urllib.request
import json
from typing import List

from .base import BaseSource
from ..models import Product

_ENDPOINT = "https://router.jd.com/api"
_METHOD = "jd.union.open.goods.query"


class JdCpsSource(BaseSource):
    platform = "jd_cps"
    platform_name = "京东联盟(官方API)"

    def __init__(self, timeout: int = 10, **kwargs):
        self.appkey = os.environ.get("PC_CPS_JD_APPKEY", "")
        self.secret = os.environ.get("PC_CPS_JD_SECRET", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def can_live(self) -> bool:
        return bool(self.appkey and self.secret)

    def _sign(self, params: dict) -> str:
        # 京东签名：参数按 key ASCII 排序，拼 secret+kv...kv+secret，MD5 大写
        items = sorted((k, str(v)) for k, v in params.items() if k not in ("sign",) and v != "")
        raw = self.secret + "".join(f"{k}{v}" for k, v in items) + self.secret
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        if not self.can_live():
            return []
        try:
            biz = {
                "goodsReqDTO": {
                    "keyword": keyword,
                    "pageIndex": max(1, page),
                    "pageSize": min(page_size, 50),
                }
            }
            params = {
                "method": _METHOD,
                "app_key": self.appkey,
                "sign": "",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "v": "1.0",
                "format": "json",
                "param_json": json.dumps(biz, ensure_ascii=False, separators=(",", ":")),
            }
            params["sign"] = self._sign(params)
            url = _ENDPOINT + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": "price-collector/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            result = data.get("jd_union_open_goods_query_responce") or data.get(
                "jd_union_open_goods_query_response") or {}
            rows = (result.get("data") or {}).get("result") or []
            out: List[Product] = []
            for it in rows:
                try:
                    price = float(it.get("price") or 0)
                    if price <= 0:
                        continue
                    out.append(Product(
                        platform="jd_cps",
                        name=(it.get("skuName") or keyword).strip(),
                        price=price,
                        original_price=float(it.get("originPrice") or 0),
                        sales=0,
                        sales_text="",
                        shop_rating=-1.0,
                        shop_name=it.get("shopName") or "",
                        url=it.get("materialUrl") or "",
                        image=(it.get("imageInfo") or {}).get("imageUrl") or "",
                        keyword=keyword,
                        raw={},
                    ))
                except Exception:
                    continue
            return out
        except Exception:
            return []
