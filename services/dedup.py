# -*- coding: utf-8 -*-
"""去重合并服务：名称归一化 + 相似度 + 热门标记 + 来源合并。

规则来源：方案 §4.2。
"""
from typing import List

from models import Item
from services.normalize import normalize_name

_PRICE_PRIORITY = {"用户": 3, "价格库": 2, "待补充": 1}


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    dp = list(range(lb + 1))
    for i in range(1, la + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, lb + 1):
            tmp = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = tmp
    return dp[lb]


def _similar(a: str, b: str) -> bool:
    na, nb = normalize_name(a), normalize_name(b)
    if na == nb:
        return True
    return _edit_distance(na, nb) <= 1


def _merge(target: Item, other: Item):
    # 热门度 = 各来源提及次数之和
    target.popularity = (target.popularity or 0) + (other.popularity or 1)
    # 来源合并（note id 集合）
    ids = {x for x in (target.source_ids or "").split(",") if x}
    ids |= {x for x in (other.source_ids or "").split(",") if x}
    target.source_ids = ",".join(sorted(ids, key=int)) if ids else None
    # 价格：用户 > 价格库 > 待补充
    if _PRICE_PRIORITY.get(other.price_source, 0) > _PRICE_PRIORITY.get(target.price_source, 0):
        target.price = other.price
        target.price_source = other.price_source
    # 缺失字段补齐
    for field in ("open_hours", "lat", "lng", "est_duration", "day"):
        if getattr(target, field) is None and getattr(other, field) is not None:
            setattr(target, field, getattr(other, field))


def dedup(items: List[Item]) -> List[Item]:
    """合并名称相同/高相似且类型相同的条目，返回候选条目集。"""
    merged: List[Item] = []
    for it in items:
        target = next(
            (m for m in merged if m.type == it.type and _similar(m.name, it.name)),
            None,
        )
        if target is None:
            merged.append(it)
        else:
            _merge(target, it)
    return merged
