# -*- coding: utf-8 -*-
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Budget:
    id: Optional[int] = None
    project_id: int = 0
    ticket_total: Optional[float] = None
    food_total: Optional[float] = None
    traffic_total: Optional[float] = None
    hotel_total: Optional[float] = None
    total: Optional[float] = None

    @classmethod
    def from_row(cls, row):
        return cls(**{k: row[k] for k in row.keys() if k in cls.__dataclass_fields__})

    def to_dict(self):
        return asdict(self)
