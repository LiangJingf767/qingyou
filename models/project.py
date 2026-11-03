# -*- coding: utf-8 -*-
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Project:
    id: Optional[int] = None
    city: str = ""
    days: int = 1
    budget: Optional[float] = None
    people: int = 1                     # 出行人数（含自己）
    start_date: Optional[str] = None    # 出发日期 YYYY-MM-DD
    preferences: Optional[str] = None   # JSON 文本
    cover: Optional[str] = None         # 封面图片相对路径（static/uploads/...）
    plan_tips: Optional[str] = None     # 生成建议（JSON 文本：字符串列表，含 AI 规划提示）
    status: str = "editing"
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row):
        return cls(**{k: row[k] for k in row.keys() if k in cls.__dataclass_fields__})

    def to_dict(self):
        return asdict(self)
