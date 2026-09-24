# -*- coding: utf-8 -*-
import json
import os
import re
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
import http.cookiejar

REPO = "afdk1991/proj-08"
BASE = "https://price-collector-demo-j4ml6bw0.edgeone.cool"


def run(args, timeout=180):
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    return p.stdout.decode("utf-8", "replace")


out = {}

# 1) 等最新 run 完成
deadline = time.time() + 540
last = None
while time.time() < deadline:
    raw = run(["gh", "run", "list", "-R", REPO, "--limit", "1",
               "--json", "databaseId,status,conclusion"])
    try:
        r = json.loads(raw)[0]
    except Exception:
        time.sleep(20)
        continue
    last = r
    if r["status"] == "completed":
        break
    time.sleep(20)

out["run"] = last

# 2) 提取部署 URL / token
token_qs = ""
deploy_url = ""
if last:
    log = run(["gh", "run", "view", str(last["databaseId"]), "--log"])
    log = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", log)
    m2 = re.findall(r"https://\S*eo_token=[a-f0-9]+&eo_time=[0-9]+", log)
    if m2:
        deploy_url = m2[-1]
        token_qs = deploy_url.split("?", 1)[1]
out["deploy_url"] = deploy_url

# 3) Cookie 会话验证
ctx = ssl._create_unverified_context()
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(jar),
    urllib.request.HTTPSHandler(context=ctx),
)
opener.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")]

res = {}


def get(path, label):
    sep = "&" if "?" in path else "?"
    url = BASE + path + sep + token_qs if token_qs else BASE + path
    try:
        with opener.open(url, timeout=90) as r:
            body = r.read().decode("utf-8", "replace")
            res[label] = {"status": r.status, "len": len(body), "head": body[:180]}
    except Exception as e:
        res[label] = {"error": repr(e)}


get("/", "index")
get("/api/health", "health")
kw = urllib.parse.quote("蓝牙耳机")
get("/api/search?keyword=" + kw + "&source=mock", "search")

# 4) 结构化解析 search
try:
    sep = "&"
    u = BASE + "/api/search?keyword=" + kw + "&source=mock" + sep + token_qs
    with opener.open(u, timeout=90) as r:
        data = json.loads(r.read().decode("utf-8"))
    recs = data.get("recommendations") or [{}]
    res["search_parsed"] = {
        "total": data.get("total"),
        "keyword": data.get("keyword"),
        "source_mode": data.get("source_mode"),
        "collected_at": data.get("collected_at"),
        "product_count": len(data.get("products", [])),
        "trend_n": len(data.get("price_trend", [])),
        "dist_n": len(data.get("price_distribution", [])),
        "stats": [(x.get("platform"), x.get("min_price"), x.get("avg_price")) for x in data.get("platform_stats", [])],
        "first_rec": recs[0].get("name"),
        "first_score": recs[0].get("score"),
        "first_label": recs[0].get("label"),
    }
except Exception as e:
    res["search_parse_error"] = repr(e)

out["http"] = res
with open("live.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("done")
