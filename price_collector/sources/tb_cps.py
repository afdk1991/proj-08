# -*- coding: utf-8 -*-
"""淘宝联盟（淘宝客 CPS）官方 API 数据源。

正规采集途径：在 pub.alimama.com 注册淘宝客，创建推广位拿到
AppKey / AppSecret / adzone_id，通过官方 API 按关键词查询商品，
返回标题、券后价、主图、推广链接。不破解网页、不碰风控。

凭据环境变量（在云函数环境变量 / GitHub Secret 中配置）：
  PC_CPS_TB_APPKEY    淘宝联盟 AppKey
  PC_CPS_TB_SECRET    淘宝联盟 AppSecret
  PC_CPS_TB_ADZONE    推广位 adzone_id（数字）

未配置凭据时 can_live=False、fetch 返回 []，不影响其它平台。
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

_ENDPOINT = "https://eco.taobao.com/router/rest"
_METHOD = "taobao.tbk.dg.material.optional"


class TbCpsSource(BaseSource):
    platform = "tb_cps"
    platform_name = "淘宝联盟(官方API)"

    def __init__(self, timeout: int = 10, **kwargs):
        # 优先环境变量，回退到构建时写入的 _cps_config（EdgeOne 云函数无环境变量注入）
        _cfg = {}
        try:
            from .. import _cps_config  # type: ignore
            _cfg = {k: getattr(_cps_config, k, "") for k in dir(_cps_config)}
        except Exception:
            pass
        self.appkey = os.environ.get("PC_CPS_TB_APPKEY", "") or _cfg.get("TB_APPKEY", "")
        self.secret = os.environ.get("PC_CPS_TB_SECRET", "") or _cfg.get("TB_SECRET", "")
        self.adzone = os.environ.get("PC_CPS_TB_ADZONE", "") or _cfg.get("TB_ADZONE", "")
        try:
            self.timeout = int(timeout or os.environ.get("PC_TIMEOUT", "10"))
        except (ValueError, TypeError):
            self.timeout = 10

    def can_live(self) -> bool:
        return bool(self.appkey and self.secret and self.adzone)

    def _sign(self, params: dict) -> str:
        # 淘宝 TOP md5 签名：参数按 key ASCII 排序，拼 secret+kv...kv+secret，MD5 大写
        items = sorted((k, str(v)) for k, v in params.items() if k != "sign" and v != "")
        raw = self.secret + "".join(f"{k}{v}" for k, v in items) + self.secret
        return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()

    def fetch(self, keyword: str, page: int = 1, page_size: int = 20) -> List[Product]:
        if not self.can_live():
            return []
        try:
            params = {
                "method": _METHOD,
                "app_key": self.appkey,
                "sign_method": "md5",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "format": "json",
                "v": "2.0",
                "adzone_id": self.adzone,
                "q": keyword,
                "page_size": min(page_size, 50),
                "page_no": max(1, page),
            }
            params["sign"] = self._sign(params)
            url = _ENDPOINT + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": "price-collector/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            resp = data.get("tbk_dg_material_optional_response", {})
            rows = (resp.get("result_list") or {}).get("map_data") or []
            out: List[Product] = []
            for it in rows:
                try:
                    price = float(it.get("zk_final_price") or 0)
                    if price <= 0:
                        continue
                    orig = float(it.get("org_price") or 0)
                    out.append(Product(
                        platform="tb_cps",
                        name=(it.get("title") or keyword).strip(),
                        price=price,
                        original_price=orig,
                        sales=0,
                        sales_text="",
                        shop_rating=-1.0,
                        shop_name=it.get("nick") or "",
                        url=it.get("item_url") or it.get("url") or "",
                        image=(it.get("pict_url") or "").replace("http://", "https://"),
                        keyword=keyword,
                        raw={},
                    ))
                except Exception:
                    continue
            return out
        except Exception:
            return []
