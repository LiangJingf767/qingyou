# -*- coding: utf-8 -*-
"""补全服务：原始实体 → 完整条目（三级价格 + 开放时间 + 坐标 + 预估耗时）。

规则来源：方案 §4.4（三级价格匹配）。
"""
from typing import List

from db import get_db
from models import Item
from services.extract import RawEntity
from services.geo_resolver import resolve

# 按类型默认预估游玩时长（分钟）
DEFAULT_DURATION = {"景点": 120, "美食": 45, "机位": 20}


def enrich(entities: List[RawEntity], city: str, db=None, project_id=None) -> List[Item]:
    """补全每个实体：价格库命中补价格/开放时间/坐标，坐标三级查找兜底（本地→高德→缓存）。"""
    db = db or get_db()
    items = []
    for e in entities:
        it = Item(
            project_id=0,   # 由管线写库时赋值
            name=e.name,
            type=e.type,
            day=e.day,
            note=e.note,
            est_duration=DEFAULT_DURATION.get(e.type),
            popularity=1,
            source_ids=str(e.source_note_id) if e.source_note_id is not None else None,
        )

        # 三级价格匹配：用户 > 价格库 > 待补充
        if e.price_source == "用户" and e.price is not None:
            it.price, it.price_source = e.price, "用户"
        else:
            row = db.execute(
                "SELECT * FROM price_lib WHERE city = ? AND name = ? LIMIT 1",
                (city, e.name),
            ).fetchone()
            if row:
                it.price, it.price_source = row["price"], "价格库"
                it.type = it.type or row["type"]
                it.open_hours = row["open_hours"]
                it.lat, it.lng = row["lat"], row["lng"]
            else:
                it.price, it.price_source = None, "待补充"

        # 坐标三级查找：本地库（price_lib / 本项目 item）→ 高德 → 写回缓存
        if it.lat is None or it.lng is None:
            lat, lng, _src = resolve(e.name, city, db, project_id=project_id)
            if lat is not None:
                it.lat, it.lng = lat, lng

        items.append(it)
    return items
