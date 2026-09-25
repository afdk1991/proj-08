# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, '.')
from price_collector.sources import _http
import re

html = _http.fetch_html('https://search.suning.com/iphone/', timeout=12)
# 找 1585 出现位置上下文
i = html.find('>1585<')
print('ctx around 1585:')
print(html[i-300:i+100].replace('\n',' '))
print('---')
# 看 res-info / price 块结构
j = html.find('res-info')
print('res-info block:')
print(html[j:j+600].replace('\n',' '))
