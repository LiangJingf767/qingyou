# -*- coding: utf-8 -*-
"""名称标准化工具（提取匹配与去重合并共用）。"""
import re

# 常见分类后缀（长后缀优先，去尾后作为「核心名」）
_SUFFIXES = [
    "博物院", "博物馆", "风景区", "步行街", "古镇", "古城", "老街",
    "景区", "公园", "广场", "小吃", "简餐", "老店",
]

# 常用繁体 → 简体（可扩展；完整转换可接入 opencc）
_TRAD_SIMP = {
    "長": "长", "臺": "台", "國": "国", "門": "门", "廣": "广",
    "場": "场", "園": "园", "館": "馆", "廟": "庙", "裡": "里", "裏": "里",
}


def to_simplified(s: str) -> str:
    return "".join(_TRAD_SIMP.get(ch, ch) for ch in s)


def normalize_name(name: str) -> str:
    """去空格、繁体转简体、去常见分类后缀。"""
    if not name:
        return ""
    n = to_simplified(name)
    n = re.sub(r"\s+", "", n)
    for suf in _SUFFIXES:
        if n.endswith(suf) and len(n) > len(suf) + 1:
            n = n[: -len(suf)]
            break
    return n


# 常被口语省略的「可省略词」（用于简称匹配，如「大熊猫基地」↔「大熊猫繁育基地」）
_FILLER_WORDS = ["繁育", "研究", "遗址", "保护区"]


def core_name(name: str) -> str:
    """归一化后再去掉常被省略的填充词，得到「核心名」，用于简称匹配。"""
    n = normalize_name(name)
    for w in _FILLER_WORDS:
        n = n.replace(w, "")
    return n
