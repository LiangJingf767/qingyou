# -*- coding: utf-8 -*-
"""生成引擎接口与 DTO。

GenerationEngine 为抽象基类：一期 RuleEngine 实现，二期 LlmEngine 同接口替换（可插拔）。
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from dto import Conflict
from models import Item


@dataclass
class GenerationRequest:
    """生成请求：项目约束（城市/天数/预算/偏好）。候选条目由引擎从 DB 读取。"""
    project_id: int
    city: str
    days: int
    budget: Optional[float] = None
    preferences: Optional[dict] = None

    @classmethod
    def from_project(cls, row):
        prefs = None
        if row["preferences"]:
            try:
                prefs = json.loads(row["preferences"])
            except (TypeError, ValueError):
                prefs = None
        return cls(
            project_id=row["id"],
            city=row["city"],
            days=row["days"] or 1,
            budget=row["budget"],
            preferences=prefs,
        )


@dataclass
class DayPlan:
    """一天的行程（条目已排序，day / order_no 已写）。"""
    day: int
    items: List[Item] = field(default_factory=list)


@dataclass
class GenerationResult:
    """生成结果：按天行程 + 冲突 + 取舍建议 + 被裁剪条目。"""
    days: List[DayPlan] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    dropped: List[Item] = field(default_factory=list)


class GenerationEngine(ABC):
    """生成引擎抽象接口：generate(request) -> GenerationResult。"""

    @abstractmethod
    def generate(self, request: GenerationRequest, db=None) -> GenerationResult:
        """输入项目约束，输出按天行程。"""
