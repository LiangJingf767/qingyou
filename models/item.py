# -*- coding: utf-8 -*-
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Item:
    id: Optional[int] = None
    project_id: int = 0
    name: str = ""
    type: Optional[str] = None
    price: Optional[float] = None
    price_source: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    open_hours: Optional[str] = None
    est_duration: Optional[int] = None
    note: Optional[str] = None          # 大模型生成的条目备注（时间段/游玩提示等）
    day: Optional[int] = None
    order_no: Optional[int] = None
    dropped: int = 0                     # 1=用户手动砍单
    popularity: int = 1
    source_ids: Optional[str] = None

    @classmethod
    def from_row(cls, row):
        return cls(**{k: row[k] for k in row.keys() if k in cls.__dataclass_fields__})

    def to_dict(self):
        return asdict(self)
