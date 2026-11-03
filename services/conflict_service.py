# -*- coding: utf-8 -*-
"""冲突检测服务：§4.6 闭馆日 / 距离过远 / 强度过高 / 预算超支。"""
import math
import re
from datetime import date, timedelta
from typing import List

from db import get_db
from dto import Conflict
from models import Item
from services.budget_service import compute_budget

# 强度阈值
MAX_DAILY_MINUTES = 600
MAX_DAILY_SPOTS = 8
# 相邻点直线距离阈值（公里）
MAX_ADJACENT_KM = 10.0

_WEEKDAY = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6, "星期天": 6}
_CLOSED_RE = re.compile(r"(周[一二三四五六日天])\s*闭馆")


def detect_conflicts(project_id: int, db=None, start_date=None) -> List[Conflict]:
    """对已排程条目做 §4.6 四类冲突检测。start_date 缺失时跳过闭馆日。"""
    db = db or get_db()
    project = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise ValueError(f"project {project_id} not found")
    items = [Item.from_row(r) for r in db.execute(
        "SELECT * FROM item WHERE project_id = ? AND day IS NOT NULL AND dropped=0 ORDER BY day, order_no",
        (project_id,),
    ).fetchall()]

    by_day = {}
    for it in items:
        by_day.setdefault(it.day, []).append(it)

    conflicts: List[Conflict] = []

    # 1. 强度过高（每日地点数 + 时长）
    for day, g in by_day.items():
        dur = sum(it.est_duration or 0 for it in g)
        if dur > MAX_DAILY_MINUTES or len(g) > MAX_DAILY_SPOTS:
            conflicts.append(Conflict(
                "强度过高",
                f"第{day}天 {len(g)} 个地点约 {dur} 分钟，超上限",
                day=day, item_ids=[it.id for it in g],
            ))

    # 2. 距离过远（相邻点直线距离，需坐标）
    for day, g in by_day.items():
        for a, b in zip(g, g[1:]):
            if a.lat is not None and a.lng is not None and b.lat is not None and b.lng is not None:
                km = _haversine(a.lat, a.lng, b.lat, b.lng)
                if km > MAX_ADJACENT_KM:
                    conflicts.append(Conflict(
                        "距离过远",
                        f"第{day}天「{a.name}」到「{b.name}」相距约 {km:.1f} km",
                        day=day, item_ids=[a.id, b.id],
                    ))

    # 3. 闭馆日（出发日期：显式参数优先，否则读 project.start_date）
    if start_date is None:
        start_date = project["start_date"]
    conflicts.extend(_closed_days(by_day, start_date))

    # 4. 预算超支
    if project["budget"] is not None:
        budget = compute_budget(items, project["city"], project["days"] or 1, "标准", db,
                                people=project["people"] or 1)
        if budget.total > project["budget"]:
            conflicts.append(Conflict(
                "预算超支",
                f"预计 {budget.total:.0f} 元，超出预算 {project['budget']:.0f} 元",
            ))

    return conflicts


def _closed_days(by_day, start_date) -> List[Conflict]:
    if start_date is None:
        return []
    try:
        d0 = date.fromisoformat(str(start_date))
    except ValueError:
        return []
    out = []
    for day, g in by_day.items():
        weekday = (d0 + timedelta(days=day - 1)).weekday()
        for it in g:
            m = _CLOSED_RE.search(it.open_hours or "")
            if m and _WEEKDAY.get(m.group(1)) == weekday:
                out.append(Conflict(
                    "闭馆日",
                    f"第{day}天「{it.name}」当天闭馆",
                    day=day, item_ids=[it.id],
                ))
    return out


def _haversine(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
