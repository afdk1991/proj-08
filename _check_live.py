# -*- coding: utf-8 -*-
"""线上整站可用性验证：首页 + /api/health + /api/search（带 Cookie 会话，模拟浏览器）。"""
import http.cookiejar
import json
import urllib.parse
import urllib.request

BASE = "https://price-collector-demo-qctxudzb.edgeone.cool"
TOKEN = "bffdd16f354ce65068cdf68955d84fc5"
EO_TIME = "1790346425"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")]
# requests 库不支持自动解压，故不声明 gzip

out = {}


def get(path, with_token=True):
    url = BASE + path
    if with_token:
        sep = "&" if "?" in path else "?"
        url += "%seo_token=%s&eo_time=%s" % (sep, TOKEN, EO_TIME)
    try:
        r = opener.open(url, timeout=30)
        body = r.read()
        try:
            text = body.decode("utf-8")
        except Exception:
            text = body.decode("utf-8", "replace")
        return r.status, text
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, "ERR: %s" % e


# 1) 先访问根路径建立会话
s0, _ = get("/")
out["home_status"] = s0

# 2) health
s, t = get("/api/health")
out["health_status"] = s
out["health_body"] = t[:300]

# 3) search
q = urllib.parse.urlencode({"keyword": "蓝牙耳机", "source": "mock"})
s, t = get("/api/search?" + q)
out["search_status"] = s
try:
    j = json.loads(t)
    out["search_total"] = j.get("total")
    out["search_source_mode"] = j.get("source_mode")
    recs = j.get("recommendations") or []
    out["search_recs"] = len(recs)
    if recs:
        out["search_top1"] = {
            "name": recs[0].get("name"),
            "score": recs[0].get("score"),
            "label": recs[0].get("label"),
        }
    out["search_has_platform_stats"] = len(j.get("platform_stats") or [])
    out["search_has_trend"] = len(j.get("price_trend") or [])
except Exception as e:
    out["search_raw"] = t[:400]
    out["search_parse_err"] = str(e)

# 4) 首页内容检查
s, t = get("/")
out["home_len"] = len(t)
out["home_has_appjs"] = "app.js" in t
out["home_has_title"] = "<title>" in t

with open("live_check.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(json.dumps(out, ensure_ascii=False, indent=2))
