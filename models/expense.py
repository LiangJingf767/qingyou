# -*- coding: utf-8 -*-
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Expense:
    id: Optional[int] = None
    project_id: int = 0
    category: Optional[str] = None
    amount: Optional[float] = None
    item_id: Optional[int] = None
    note: Optional[str] = None
    spent_at: Optional[str] = None

    @classmethod
    def from_row(cls, row):
        return cls(**{k: row[k] for k in row.keys() if k in cls.__dataclass_fields__})

    def to_dict(self):
        return asdict(self)
