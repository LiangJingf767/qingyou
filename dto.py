# -*- coding: utf-8 -*-
"""跨层共享 DTO（引擎 / 冲突检测 / 预算服务共用）。"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Conflict:
    """冲突检测结果。"""
    type: str                          # 闭馆日 / 距离过远 / 强度过高 / 预算超支
    message: str
    day: Optional[int] = None
    item_ids: List[int] = field(default_factory=list)


@dataclass
class BudgetResult:
    """预算明细（§4.5）。"""
    ticket_total: float
    food_total: float
    traffic_total: float
    hotel_total: float
    total: float
    tier: str = "标准"
