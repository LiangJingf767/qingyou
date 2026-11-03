# -*- coding: utf-8 -*-
"""行程诊断：把当前行程打包成一段清晰文本，交给大模型审查并给出「人话」建议。

大模型返回结构化建议列表，每条含 title / body / action（action 可驱动前端「采纳」：
drop:地点名 或 move:地点名:第N天，无直接操作留空）。
"""
import json
import re

from db import get_db
from models import Item
from services.budget_service import compute_budget
from services.conflict_service import _haversine
from services.llm_service import call_llm

_SYSTEM = (
    "你是经验丰富的旅行行程审查员（专业向导）。用户给你一段行程概况，"
    "请像向导一样找出其中不合理之处（某天排太满、预算快超、地点距离太远不顺路等），"
    "只给最有价值、可执行的建议。严格要求：只输出一个 JSON 对象，"
    "不要任何解释，不要用 markdown 代码块，保证是合法 JSON。"
)

_JSON_TEMPLATE = json.dumps({
    "suggestions": [
        {
            "title": "简短标题（如：Day2 行程太满）",
            "body": "人话建议，具体到哪一天、哪个地点、怎么改",
            "action": "可选：drop:地点名 或 move:地点名:第N天；无直接操作则留空字符串",
        }
    ]
}, ensure_ascii=False)


def build_diagnosis_summary(project_id: int, db=None) -> str:
    """把当前行程概况（预算 + 每天点位 + 相邻点直线距离）打包成文本。"""
    db = db or get_db()
    project = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise ValueError(f"project {project_id} not found")
    items = [Item.from_row(r) for r in db.execute(
        "SELECT * FROM item WHERE project_id = ? AND day IS NOT NULL AND dropped=0 "
        "ORDER BY day, order_no",
        (project_id,),
    ).fetchall()]
    budget = compute_budget(items, project["city"], project["days"] or 1, "标准", db,
                            people=project["people"] or 1)

    lines = [
        f"目的地：{project['city']}，共 {project['days'] or 1} 天，{project['people'] or 1} 人",
        f"预算上限：{project['budget'] if project['budget'] is not None else '未设'} 元；"
        f"当前核算总花费约 {budget.total:.0f} 元"
        f"（门票 {budget.ticket_total:.0f} / 餐饮 {budget.food_total:.0f} / "
        f"交通 {budget.traffic_total:.0f} / 住宿 {budget.hotel_total:.0f}）",
        "",
    ]
    by_day = {}
    for it in items:
        by_day.setdefault(it.day, []).append(it)
    for day in sorted(by_day):
        g = by_day[day]
        total_min = sum(it.est_duration or 0 for it in g)
        lines.append(f"Day{day}（{len(g)} 个点，约 {total_min} 分钟）：")
        for it in g:
            price = f"{it.price:.0f}元" if it.price is not None else "免费/待定"
            lines.append(f"  - {it.name}｜{it.type or '待定'}｜{price}｜约{it.est_duration or '?'}分钟")
        for a, b in zip(g, g[1:]):
            if None not in (a.lat, a.lng, b.lat, b.lng):
                km = _haversine(a.lat, a.lng, b.lat, b.lng)
                lines.append(f"    （{a.name} → {b.name} 直线约 {km:.1f} km）")
        lines.append("")
    return "\n".join(lines)


def _parse_json(content: str) -> dict:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    else:
        text = re.sub(r"^```|```$", "", text).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e > s:
            obj = json.loads(text[s:e + 1])
        else:
            raise
    if not isinstance(obj, dict):
        raise ValueError("大模型返回不是对象")
    return obj


def diagnose(project_id: int, llm_config: dict, db=None) -> list:
    """调用大模型审查行程，返回建议列表（每项 dict：title/body/action）。"""
    db = db or get_db()
    summary = build_diagnosis_summary(project_id, db)
    user = (
        summary
        + "\n\n请审查上面这份行程，输出 JSON："
        + _JSON_TEMPLATE
        + "\n（action 里的地点名必须与上面行程中的地点名完全一致；最多 5 条建议）"
    )
    content = call_llm(llm_config, [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ])
    obj = _parse_json(content)
    return obj.get("suggestions") or []
