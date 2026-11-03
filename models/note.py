# -*- coding: utf-8 -*-
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Note:
    id: Optional[int] = None
    project_id: int = 0
    text: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row):
        return cls(**{k: row[k] for k in row.keys() if k in cls.__dataclass_fields__})

    def to_dict(self):
        return asdict(self)
