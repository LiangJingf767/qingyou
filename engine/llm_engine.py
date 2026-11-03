# -*- coding: utf-8 -*-
"""LlmEngine：BYOK 大模型行程生成引擎。

与 RuleEngine 同接口（GenerationEngine）。用户自填 API 时，用大模型在
意向条目基础上「自由补充完善」，输出按天行程 + 条目备注 + 整体建议。
失败时由路由回退 RuleEngine。
"""
import json
import re

from db import get_db
from models import Item
from engine.base import GenerationEngine, GenerationResult, DayPlan
from services.llm_service import call_llm
from services.normalize import normalize_name, core_name
from services.conflict_service import detect_conflicts
from services.geo_resolver import resolve

_ALLOWED_TYPES = ("景点", "美食", "机位")

_SYSTEM = (
    "你是资深的穷游行程规划师，擅长为大学生设计省钱又有趣的路线。"
    "请根据用户提供的信息生成个性化行程。严格要求：只输出一个 JSON 对象，"
    "不要输出任何解释，不要用 markdown 代码块（不要用 ``` 包裹），保证是合法 JSON。"
)


class LlmEngine(GenerationEngine):
    def generate(self, request, llm_config, db=None) -> GenerationResult:
        db = db or get_db()
        project = db.execute(
            "SELECT * FROM project WHERE id = ?", (request.project_id,),
        ).fetchone()
        if project is None:
            raise ValueError(f"project {request.project_id} not found")

        existing = [Item.from_row(r) for r in db.execute(
            "SELECT * FROM item WHERE project_id = ? ORDER BY id", (request.project_id,),
        ).fetchall()]

        prompt = self._build_prompt(project, existing, db)
        content = call_llm(llm_config, [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ])
        obj = self._parse_json(content)

        # 解析 → 条目（复用已有条目做名称匹配，保留权威价格/坐标）
        plan_days = obj.get("days") or []
        scheduled, used = self._plan_to_items(plan_days, existing, request.project_id)
        self._persist(scheduled, used, existing, project["city"], db)

        suggestions = self._collect_tips(plan_days, obj)
        conflicts = detect_conflicts(request.project_id, db)

        max_day = max([request.days, *(d for d, _, _ in scheduled)], default=request.days)
        day_map = {}
        for d, _, it in scheduled:
            day_map.setdefault(d, []).append(it)
        return GenerationResult(
            days=[DayPlan(day=d, items=day_map.get(d, [])) for d in range(1, max_day + 1)],
            conflicts=conflicts,
            suggestions=suggestions,
            dropped=[],
        )

    # ---- 提示词 ----
    def _build_prompt(self, project, existing, db) -> str:
        cfg = db.execute(
            "SELECT transit_avg, meal_avg, hostel_avg FROM city_config WHERE city = ?",
            (project["city"],),
        ).fetchone()
        transit = (cfg["transit_avg"] or 0) if cfg else 0
        meal = (cfg["meal_avg"] or 0) if cfg else 0
        hostel = (cfg["hostel_avg"] or 0) if cfg else 0
        people = project["people"] or 1

        lines = [
            f"目的地：{project['city']}",
            f"天数：{project['days'] or 1} 天",
            f"总预算：{project['budget'] if project['budget'] is not None else '不限'} 元",
            f"人数：{people} 人",
            f"兴趣偏好：{project['preferences'] or '无'}",
            f"出发日期：{project['start_date'] or '未定'}",
            f"人均日均参考：交通 {transit} 元 / 餐饮 {meal} 元 / 青旅住宿 {hostel} 元",
            "",
        ]
        if existing:
            lines.append("用户笔记中提取的意向地点（需优先保留并安排）：")
            for it in existing:
                p = f"{it.price}元" if it.price is not None else "价格待定"
                hint = f"｜期望第{it.day}天" if it.day else ""
                lines.append(f"- {it.name}｜类型{it.type or '待定'}｜{p}｜约{it.est_duration or '?'}分钟{hint}")
        else:
            lines.append("用户未提供意向地点，请完全根据城市与偏好自由规划。")
        lines.append("")
        lines.append(
            "请输出如下 JSON 结构（items 的 type 只能是 景点/美食/机位；price 为估算金额、"
            "不确定填 null；duration_min 为预估停留分钟；time 用 HH:MM）："
        )
        lines.append(json.dumps({
            "days": [
                {"day": 1, "theme": "当天主题",
                 "items": [{"name": "地点名", "type": "景点", "time": "08:00",
                            "duration_min": 120, "price": 55, "note": "游玩提示"}],
                 "tip": "当天小贴士（交通/节奏/美食建议）"}
            ],
            "suggestions": ["整体建议（预算分配、节奏提醒等）"],
        }, ensure_ascii=False))
        return "\n".join(lines)

    # ---- JSON 解析 ----
    def _parse_json(self, content: str) -> dict:
        text = content.strip()
        # 去掉可能的 ```json ... ``` 包裹
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        else:
            text = re.sub(r"^```|```$", "", text).strip()
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            # 兜底：截取首个 { 到末个 }
            s = text.find("{")
            e = text.rfind("}")
            if s >= 0 and e > s:
                obj = json.loads(text[s:e + 1])
            else:
                raise
        if not isinstance(obj, dict):
            raise ValueError("大模型返回不是对象")
        return obj

    # ---- 条目映射 ----
    def _plan_to_items(self, plan_days, existing, project_id):
        by_norm, by_core = {}, {}
        for it in existing:
            by_norm.setdefault(normalize_name(it.name), []).append(it)
            by_core.setdefault(core_name(it.name), []).append(it)
        used = set()
        scheduled = []
        for di, day_obj in enumerate(plan_days, start=1):
            try:
                day = int(day_obj.get("day") or di)
            except (TypeError, ValueError):
                day = di
            for oi, e in enumerate(day_obj.get("items") or [], start=1):
                name = (e.get("name") or "").strip()
                if not name:
                    continue
                typ = e.get("type") if e.get("type") in _ALLOWED_TYPES else "景点"
                dur = e.get("duration_min")
                price = e.get("price")
                note = self._fmt_note(e)

                matches = by_norm.get(normalize_name(name)) or by_core.get(core_name(name)) or []
                it = next((m for m in matches if m.id not in used), None)
                if it is not None:
                    used.add(it.id)
                    it.day, it.order_no = day, oi
                    if dur is not None:
                        it.est_duration = int(dur)
                    if note:
                        it.note = note
                    if not it.type:
                        it.type = typ
                else:
                    it = Item(
                        project_id=project_id, name=name, type=typ,
                        price=price, price_source="大模型",
                        est_duration=int(dur) if dur is not None else None,
                        note=note, popularity=1,
                    )
                scheduled.append((day, oi, it))
        return scheduled, used

    @staticmethod
    def _fmt_note(e) -> str:
        parts = [p for p in [(e.get("time") or "").strip(), (e.get("note") or "").strip()] if p]
        return " · ".join(parts) or None

    # ---- 写回 ----
    def _persist(self, scheduled, used, existing, city, db):
        # 未出现在大模型方案里的已有条目 → 取消排程（保留为候选）
        for it in existing:
            if it.id is None or it.id in used:
                continue
            db.execute("UPDATE item SET day=NULL, order_no=NULL WHERE id=?", (it.id,))
        for day, order, it in scheduled:
            if it.id is not None:
                db.execute(
                    "UPDATE item SET day=?, order_no=?, est_duration=?, note=?, type=? WHERE id=?",
                    (day, order, it.est_duration, it.note, it.type, it.id),
                )
            else:
                lat, lng, _src = resolve(it.name, city, db)
                cur = db.execute(
                    "INSERT INTO item (project_id, name, type, price, price_source, "
                    "est_duration, note, day, order_no, popularity, lat, lng) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (it.project_id, it.name, it.type, it.price, it.price_source,
                     it.est_duration, it.note, day, order, it.popularity, lat, lng),
                )
                it.id = cur.lastrowid
        db.commit()

    # ---- 建议 ----
    def _collect_tips(self, plan_days, obj) -> list:
        tips = []
        for day_obj in plan_days:
            tip = (day_obj.get("tip") or "").strip()
            if not tip:
                continue
            theme = (day_obj.get("theme") or "").strip()
            label = f"Day{day_obj.get('day', '')} "
            tips.append(label + (theme + " · " if theme else "") + tip)
        for s in obj.get("suggestions") or []:
            if isinstance(s, str) and s.strip():
                tips.append(s.strip())
        return tips
