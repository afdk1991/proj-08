# -*- coding: utf-8 -*-
"""平台权威注册表（单一事实源）。

键名 / 中文名在此统一定义，前端、分析、CLI 全部从这里派生，
不再在各处写死。键名与 PLATFORM_SPEC.md 保持一致，共 31 个平台。
"""

# 全部平台键（顺序即展示顺序）；末尾两个 *cps 为官方 API 正规数据源
ALL_PLATFORMS = [
    "jd", "taobao", "pdd", "tmall", "vip", "suning",
    "douyin", "kuaishou", "wechat", "xiaohongshu", "c1688",
    "meituan", "jdnow", "tbflash", "hema",
    "dewu", "yanxuan", "miyoupin", "xianyu", "zhuanzhuan",
    "tmallglobal", "jdglobal", "kaola", "douyinglobal",
    "temu", "shein", "tiktokshop", "aliexpress",
    "shopee", "lazada", "amazon",
    "tb_cps", "jd_cps",
]

# 键 -> 中文名
PLATFORM_NAMES = {
    "jd": "京东",
    "taobao": "淘宝",
    "pdd": "拼多多",
    "tmall": "天猫",
    "vip": "唯品会",
    "suning": "苏宁易购",
    "douyin": "抖音电商",
    "kuaishou": "快手电商",
    "wechat": "微信小店",
    "xiaohongshu": "小红书",
    "c1688": "1688",
    "meituan": "美团闪购",
    "jdnow": "京东秒送",
    "tbflash": "淘宝闪购",
    "hema": "盒马",
    "dewu": "得物",
    "yanxuan": "网易严选",
    "miyoupin": "小米有品",
    "xianyu": "闲鱼",
    "zhuanzhuan": "转转",
    "tmallglobal": "天猫国际",
    "jdglobal": "京东国际",
    "kaola": "考拉海购",
    "douyinglobal": "抖音全球购",
    "temu": "Temu",
    "shein": "SHEIN",
    "tiktokshop": "TikTok Shop",
    "aliexpress": "AliExpress",
    "shopee": "Shopee",
    "lazada": "Lazada",
    "amazon": "Amazon",
    "tb_cps": "淘宝联盟·官方API",
    "jd_cps": "京东联盟·官方API",
}

# 键 -> 所属公司
PLATFORM_COMPANIES = {
    "jd": "京东集团", "taobao": "阿里巴巴", "pdd": "PDD Holdings",
    "tmall": "阿里巴巴", "vip": "唯品会", "suning": "苏宁易购",
    "douyin": "字节跳动", "kuaishou": "快手", "wechat": "腾讯",
    "xiaohongshu": "小红书", "c1688": "阿里巴巴",
    "meituan": "美团", "jdnow": "京东集团", "tbflash": "阿里巴巴", "hema": "阿里巴巴",
    "dewu": "上海识装科技", "yanxuan": "网易", "miyoupin": "小米集团",
    "xianyu": "阿里巴巴", "zhuanzhuan": "转转集团",
    "tmallglobal": "阿里巴巴", "jdglobal": "京东集团", "kaola": "阿里巴巴",
    "douyinglobal": "字节跳动",
    "temu": "PDD Holdings", "shein": "SHEIN", "tiktokshop": "字节跳动",
    "aliexpress": "阿里巴巴", "shopee": "Sea Group", "lazada": "阿里巴巴",
    "amazon": "亚马逊",
    "tb_cps": "阿里巴巴(淘宝联盟)", "jd_cps": "京东集团(京东联盟)",
}
