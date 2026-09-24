# -*- coding: utf-8 -*-
"""把 web/ 三件套内联为单文件 HTML，供 EdgeOne Makers 单值部署。

EdgeOne deploy_html 只接受一份 HTML 内容，因此将 style.css 与 app.js
内联进 index.html，保留外部 ECharts CDN。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
OUT = os.path.join(ROOT, "deploy", "price_collector_standalone.html")


def read(name):
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


def main():
    html = read("index.html")
    css = read("style.css")
    js = read("app.js")

    # 内联 CSS
    new_html, n_css = re.subn(
        r'<link rel="stylesheet" href="/style\.css"\s*/?>',
        lambda m: "<style>\n" + css + "\n</style>",
        html,
        count=1,
    )
    # 内联 JS
    new_html, n_js = re.subn(
        r'<script src="/app\.js"></script>',
        lambda m: "<script>\n" + js + "\n</script>",
        new_html,
        count=1,
    )

    problems = []
    if n_css != 1:
        problems.append("CSS link 替换失败")
    if n_js != 1:
        problems.append("JS script 替换失败")
    if 'href="/style.css"' in new_html:
        problems.append("仍残留外部 CSS 引用")
    if 'src="/app.js"' in new_html:
        problems.append("仍残留外部 JS 引用")
    if "<style>" not in new_html or "</style>" not in new_html:
        problems.append("缺少内联 style 标签")
    if new_html.count("<script>") < 1 or "</script>" not in new_html:
        problems.append("缺少内联 script 标签")
    # 简单的 JS 语法检查：把内联 script 抽出来交给 node
    scripts = re.findall(r"<script>(.*?)</script>", new_html, flags=re.S)
    for s in scripts:
        if "</script" in s or "<script" in s:
            problems.append("内联 JS 中疑似出现嵌套 script 标签")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(new_html)

    if problems:
        print("校验失败:")
        for p in problems:
            print(" -", p)
        sys.exit(1)

    print("已生成:", OUT)
    print("大小:", os.path.getsize(OUT), "bytes")
    print("CSS 内联: %d 处 | JS 内联: %d 处" % (n_css, n_js))


if __name__ == "__main__":
    main()
