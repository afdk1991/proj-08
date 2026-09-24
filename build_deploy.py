# -*- coding: utf-8 -*-
"""部署装配脚本：把「整个项目」打包成 EdgeOne Makers 可部署目录 deploy/。

deploy/ 结构（静态文件与云函数同域部署，前端直接 fetch('/api/search')，无需跨域）：
    deploy/
    ├── index.html, app.js, style.css      # 前端静态资源
    ├── cloud-functions/
    │   ├── api/health.py                  # GET /api/health
    │   ├── api/search.py                  # GET /api/search
    │   └── price_collector/               # 采集包（辅助模块，必须在此才会随函数打包）
    └── price_collector/                   # 项目根兜底副本

关键：构建器只扫描 cloud-functions/ 下的 .py 作为辅助模块，
      因此 price_collector 必须位于 cloud-functions/ 内，否则函数导入失败会静默 404。
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.join(ROOT, "deploy")

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def _copytree(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=IGNORE)


def build():
    # 干净重建
    if os.path.exists(DEPLOY):
        shutil.rmtree(DEPLOY)
    os.makedirs(DEPLOY, exist_ok=True)

    # 1) 前端静态资源
    for f in ("index.html", "app.js", "style.css"):
        s = os.path.join(ROOT, "web", f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(DEPLOY, f))

    # 2) 云函数（先整体复制，之后再往内塞辅助包，避免被 rmtree 清掉）
    _copytree(
        os.path.join(ROOT, "cloud-functions"),
        os.path.join(DEPLOY, "cloud-functions"),
    )

    # 3) 采集包放入 cloud-functions/ 内（关键）
    _copytree(
        os.path.join(ROOT, "price_collector"),
        os.path.join(DEPLOY, "cloud-functions", "price_collector"),
    )

    # 4) 项目根兜底副本
    _copytree(
        os.path.join(ROOT, "price_collector"),
        os.path.join(DEPLOY, "price_collector"),
    )

    # 校验
    checks = [
        os.path.join(DEPLOY, "index.html"),
        os.path.join(DEPLOY, "app.js"),
        os.path.join(DEPLOY, "style.css"),
        os.path.join(DEPLOY, "cloud-functions", "api", "search.py"),
        os.path.join(DEPLOY, "cloud-functions", "api", "health.py"),
        os.path.join(DEPLOY, "cloud-functions", "price_collector", "__init__.py"),
        os.path.join(DEPLOY, "cloud-functions", "price_collector", "pipeline.py"),
        os.path.join(DEPLOY, "price_collector", "__init__.py"),
    ]
    miss = [c for c in checks if not os.path.exists(c)]
    if miss:
        print("缺失文件:", miss, file=sys.stderr)
        sys.exit(1)

    print("部署目录已生成:", DEPLOY)
    print("  - 前端静态:", os.path.join(DEPLOY, "index.html"))
    print("  - 云函数:", os.path.join(DEPLOY, "cloud-functions", "api", "search.py"))
    print("  - 采集包(随函数打包):", os.path.join(DEPLOY, "cloud-functions", "price_collector"))


if __name__ == "__main__":
    build()
