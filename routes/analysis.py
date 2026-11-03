# -*- coding: utf-8 -*-
"""预算、冲突检测与 AI 行程诊断路由。"""
import json
import re
from dataclasses import asdict

from flask import Blueprint, request

from db import get_db
from models import Item
from response import ok, not_found, fail, bad_request, CODE_BIZ_ERROR, CODE_EXT_ERROR
from services.budget_service import calc_budget, suggest_tradeoffs, suggest_tradeoff_items
from services.conflict_service import detect_conflicts
from services.diagnose_service import diagnose
from services.llm_service import LlmError
from services.normalize import normalize_name, core_name

bp = Blueprint("analysis", __name__, url_prefix="/api/v1")


def _project_row(pid):
    return get_db().execute("SELECT * FROM project WHERE id = ?", (pid,)).fetchone()


@bp.route("/projects/<int:pid>/budget", methods=["GET"])
def budget(pid):
    """预算核算（§4.5），?tier=省钱|标准|舒适，附超支砍单建议。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    tier = request.args.get("tier") or "标准"
    try:
        b = calc_budget(pid, tier=tier)
        suggestions = suggest_tradeoffs(pid, tier=tier)
        tradeoffs = suggest_tradeoff_items(pid, tier=tier)
    except ValueError as e:
        return fail(CODE_BIZ_ERROR, str(e))
    return ok({"budget": asdict(b), "suggestions": suggestions, "tradeoffs": tradeoffs})


@bp.route("/projects/<int:pid>/conflicts", methods=["GET"])
def conflicts(pid):
    """冲突检测（§4.6）：闭馆日 / 距离过远 / 强度过高 / 预算超支。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    confs = detect_conflicts(pid)
    return ok([asdict(c) for c in confs])


@bp.route("/projects/<int:pid>/diagnose", methods=["POST"])
def diagnose_route(pid):
    """AI 行程诊断：把行程概况发给用户配置的大模型，返回人话建议列表。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    data = request.get_json(silent=True) or {}
    llm_cfg = data.get("llm")
    if not (isinstance(llm_cfg, dict) and llm_cfg.get("api_key")):
        return fail(CODE_BIZ_ERROR, "请先在「设置」页配置大模型（BYOK）")
    try:
        suggestions = diagnose(pid, llm_cfg)
    except (LlmError, ValueError, json.JSONDecodeError) as e:
        return fail(CODE_EXT_ERROR, f"AI 诊断失败：{e}")
    return ok({"suggestions": suggestions})


@bp.route("/projects/<int:pid>/diagnose/apply", methods=["POST"])
def diagnose_apply_route(pid):
    """采纳一条 AI 建议：action = drop:地点名 或 move:地点名:第N天。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()
    if not action:
        return bad_request("缺少 action")

    db = get_db()
    items = [Item.from_row(r) for r in db.execute(
        "SELECT * FROM item WHERE project_id = ?", (pid,)).fetchall()]

    def find(name):
        return next(
            (it for it in items
             if normalize_name(it.name) == normalize_name(name)
             or core_name(it.name) == core_name(name)),
            None,
        )

    if action.startswith("drop:"):
        name = action[5:].strip()
        it = find(name)
        if it is None:
            return fail(CODE_BIZ_ERROR, f"未找到地点「{name}」，请手动调整")
        db.execute("UPDATE item SET dropped=1 WHERE id=?", (it.id,))
        db.commit()
        return ok({"message": f"已从行程移除「{name}」"})

    if action.startswith("move:"):
        rest = action[5:].strip()
        name, _, day_s = rest.rpartition(":")
        day_s = re.sub(r"[^\d]", "", day_s)   # 兼容 "Day3" / "第3天" / "3"
        if not name or not day_s:
            return bad_request("action 格式应为 move:地点名:第N天")
        day = int(day_s)
        it = find(name)
        if it is None:
            return fail(CODE_BIZ_ERROR, f"未找到地点「{name}」，请手动调整")
        max_ord = db.execute(
            "SELECT COALESCE(MAX(order_no),0) FROM item WHERE project_id=? AND day=?",
            (pid, day),
        ).fetchone()[0]
        db.execute("UPDATE item SET day=?, order_no=? WHERE id=?", (day, max_ord + 1, it.id))
        db.commit()
        return ok({"message": f"已把「{name}」挪到 Day {day}"})

    return bad_request("无法识别的 action")
