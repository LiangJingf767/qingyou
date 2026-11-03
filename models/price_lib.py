# -*- coding: utf-8 -*-
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class PriceLib:
    id: Optional[int] = None
    city: Optional[str] = None
    name: str = ""
    type: Optional[str] = None
    price: Optional[float] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    open_hours: Optional[str] = None

    @classmethod
    def from_row(cls, row):
        return cls(**{k: row[k] for k in row.keys() if k in cls.__dataclass_fields__})

    def to_dict(self):
        return asdict(self)
