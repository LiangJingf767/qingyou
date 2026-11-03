# -*- coding: utf-8 -*-
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class CityConfig:
    city: str = ""
    transit_avg: Optional[float] = None
    hostel_avg: Optional[float] = None
    meal_avg: Optional[float] = None

    @classmethod
    def from_row(cls, row):
        return cls(**{k: row[k] for k in row.keys() if k in cls.__dataclass_fields__})

    def to_dict(self):
        return asdict(self)
