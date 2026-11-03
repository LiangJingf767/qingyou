# -*- coding: utf-8 -*-
"""预算服务：§4.5 预算公式 + 省钱/舒适档 + 取舍建议。"""
import json
import re
from typing import List

from db import get_db
from dto import BudgetResult
from models import Item

# 档位系数：作用在住宿与餐饮上（门票/交通固定）
TIER_FACTOR = {"省钱": 0.7, "标准": 1.0, "舒适": 1.5}

# 偏好标签 → 条目类型（兴趣匹配用；「省钱/舒适」与类型无关，作用于档位）
_PREF_TO_TYPE = {
    "景点": "景点", "文化": "景点", "历史": "景点", "博物馆": "景点", "休闲": "景点",
    "美食": "美食", "吃": "美食", "小吃": "美食", "餐厅": "美食",
    "机位": "机位", "拍照": "机位", "打卡": "机位",
}
_PREF_KEYS = ["偏好", "preferences", "types", "interest", "prefer"]


def value_ratio(item: Item, preferences) -> float:
    """性价比 = (热门度 × 兴趣匹配) ÷ (门票 + 通勤 + 耗时成本)。"""
    cost = (item.price or 0) + 0 + (item.est_duration or 0) / 60.0
    if cost <= 0:
        cost = 0.1
    return ((item.popularity or 1) * _interest_score(item.type, preferences)) / cost


def compute_budget(items: List[Item], city: str, days: int, tier: str = "标准", db=None, people: int = 1) -> BudgetResult:
    """§4.5 预算公式：门票 + 餐饮 + 交通 + 住宿。

    city_config 的 transit_avg/hostel_avg/meal_avg 均为「人均日均」，因此
    各项先按单人计算，再乘以同行人数得到团队总预算；人均 = 总预算 ÷ 人数。
    """
    db = db or get_db()
    row = db.execute(
        "SELECT transit_avg, hostel_avg, meal_avg FROM city_config WHERE city = ?", (city,),
    ).fetchone()
    transit = (row["transit_avg"] or 0) if row else 0
    hostel = (row["hostel_avg"] or 0) if row else 0
    meal = (row["meal_avg"] or 0) if row else 0
    factor = TIER_FACTOR.get(tier, 1.0)
    people = max(1, people or 1)

    ticket = sum(it.price or 0 for it in items if it.type == "景点")
    foods = [it for it in items if it.type == "美食"]
    food = sum(it.price or 0 for it in foods) if foods else days * meal * factor
    traffic = days * transit
    hotel = days * hostel * factor
    return BudgetResult(
        ticket_total=round(ticket * people, 2),
        food_total=round(food * people, 2),
        traffic_total=round(traffic * people, 2),
        hotel_total=round(hotel * people, 2),
        total=round((ticket + food + traffic + hotel) * people, 2),
        tier=tier,
    )


def calc_budget(project_id: int, tier: str = "标准", db=None) -> BudgetResult:
    """读取项目 + 已排程条目，按 §4.5 计算并写回 budget 表。"""
    db = db or get_db()
    project = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise ValueError(f"project {project_id} not found")
    items = [Item.from_row(r) for r in db.execute(
        "SELECT * FROM item WHERE project_id = ? AND day IS NOT NULL AND dropped=0", (project_id,),
    ).fetchall()]
    result = compute_budget(items, project["city"], project["days"] or 1, tier, db,
                            people=project["people"] or 1)

    db.execute("DELETE FROM budget WHERE project_id = ?", (project_id,))
    db.execute(
        "INSERT INTO budget (project_id, ticket_total, food_total, traffic_total, hotel_total, total) "
        "VALUES (?,?,?,?,?,?)",
        (project_id, result.ticket_total, result.food_total, result.traffic_total,
         result.hotel_total, result.total),
    )
    db.commit()
    return result


def suggest_tradeoffs(project_id: int, tier: str = "标准", db=None) -> List[str]:
    """超支时按性价比给出砍单建议（§4.6 预算超支 → 按性价比砍单）。"""
    db = db or get_db()
    project = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if project is None or project["budget"] is None:
        return []
    items = [Item.from_row(r) for r in db.execute(
        "SELECT * FROM item WHERE project_id = ? AND day IS NOT NULL AND dropped=0", (project_id,),
    ).fetchall()]
    result = compute_budget(items, project["city"], project["days"] or 1, tier, db,
                            people=project["people"] or 1)
    if result.total <= project["budget"]:
        return []
    over = result.total - project["budget"]
    prefs = _parse_prefs(project["preferences"])
    ranked = sorted(items, key=lambda it: value_ratio(it, prefs))
    return [f"超支约 {over:.0f} 元，可优先砍：{'、'.join(it.name for it in ranked[:3])}"]


def suggest_tradeoff_items(project_id: int, tier: str = "标准", db=None) -> List[dict]:
    """结构化砍单建议（供前端「砍单建议卡」）：超支时按性价比升序返回可砍条目。"""
    db = db or get_db()
    project = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if project is None or project["budget"] is None:
        return []
    items = [Item.from_row(r) for r in db.execute(
        "SELECT * FROM item WHERE project_id = ? AND day IS NOT NULL AND dropped=0",
        (project_id,),
    ).fetchall()]
    result = compute_budget(items, project["city"], project["days"] or 1, tier, db,
                            people=project["people"] or 1)
    if result.total <= project["budget"]:
        return []
    prefs = _parse_prefs(project["preferences"])
    ranked = sorted(items, key=lambda it: value_ratio(it, prefs))
    return [
        {
            "item_id": it.id,
            "name": it.name,
            "type": it.type,
            "price": it.price,
            "day": it.day,
            "reason": "性价比偏低，可优先砍",
        }
        for it in ranked[:4]
    ]


# ---- 兴趣匹配 ----
def _interest_score(item_type, preferences) -> float:
    if not item_type or not preferences:
        return 1.0
    preferred = _preferred_types(preferences)
    if not preferred:
        return 1.0
    return 1.5 if item_type in preferred else 0.8


def _preferred_types(preferences) -> set:
    return {_PREF_TO_TYPE[t] for t in _extract_tags(preferences) if t in _PREF_TO_TYPE}


def _extract_tags(preferences) -> list:
    if isinstance(preferences, list):
        return [str(x) for x in preferences]
    if isinstance(preferences, str):
        return re.split(r"[，,、\s]+", preferences.strip())
    if isinstance(preferences, dict):
        for k in _PREF_KEYS:
            v = preferences.get(k)
            if isinstance(v, (list, str)):
                return _extract_tags(v)
    return []


def _parse_prefs(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None
