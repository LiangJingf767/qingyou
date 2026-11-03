# -*- coding: utf-8 -*-
"""数据管线与行程生成路由。"""
import json
import os
import time

from flask import Blueprint, current_app, request

from db import get_db
from models import Item
from response import ok, not_found, fail, bad_request, CODE_BIZ_ERROR, CODE_EXT_ERROR
from services.pipeline import run_pipeline
from services.ocr_service import ocr_image, OcrError
from services.geo_resolver import resolve
from engine import RuleEngine, LlmEngine, GenerationRequest

bp = Blueprint("engine", __name__, url_prefix="/api/v1")

_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _project_row(pid):
    return get_db().execute("SELECT * FROM project WHERE id = ?", (pid,)).fetchone()


def _serialize_result(result):
    """GenerationResult → 前端友好的字典。"""
    return {
        "days": [
            {"day": dp.day, "items": [it.to_dict() for it in dp.items]}
            for dp in result.days
        ],
        "conflicts": [
            {"type": c.type, "message": c.message, "day": c.day, "item_ids": c.item_ids}
            for c in result.conflicts
        ],
        "suggestions": result.suggestions,
        "dropped": [it.to_dict() for it in result.dropped],
    }


@bp.route("/ocr", methods=["POST"])
def ocr_route():
    """截图 OCR：multipart 上传图片，返回识别文本 {text}。"""
    f = request.files.get("file")
    if f is None or not f.filename:
        return bad_request("缺少图片文件")
    try:
        text = ocr_image(f.read())
    except OcrError as e:
        return fail(CODE_EXT_ERROR, str(e))
    return ok({"text": text})


@bp.route("/projects/<int:pid>/pipeline", methods=["POST"])
def run_pipeline_route(pid):
    """跑管线：笔记 → 候选条目集（写库）。body 可带 {llm: cfg} 用大模型提取，否则正则。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    data = request.get_json(silent=True) or {}
    llm_config = data.get("llm")
    try:
        items = run_pipeline(pid, llm_config=llm_config)
    except ValueError as e:
        return fail(CODE_BIZ_ERROR, str(e))
    return ok({"count": len(items), "items": [it.to_dict() for it in items]})


@bp.route("/projects/<int:pid>/items", methods=["GET"])
def list_items(pid):
    """候选条目列表。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    db = get_db()
    rows = db.execute("SELECT * FROM item WHERE project_id = ? ORDER BY id", (pid,)).fetchall()
    return ok([Item.from_row(r).to_dict() for r in rows])


@bp.route("/projects/<int:pid>/items", methods=["POST"])
def create_item(pid):
    """手动录入条目（录入页「手动填表」）。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return bad_request("缺少参数 name")
    db = get_db()
    cur = db.execute(
        "INSERT INTO item (project_id, name, type, price, price_source, lat, lng, "
        "open_hours, est_duration, day, order_no, popularity) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, name, data.get("type"), data.get("price"), data.get("price_source") or "手动",
         data.get("lat"), data.get("lng"), data.get("open_hours"),
         data.get("est_duration"), data.get("day"), data.get("order_no"), 1),
    )
    db.commit()
    row = db.execute("SELECT * FROM item WHERE id = ?", (cur.lastrowid,)).fetchone()
    return ok(Item.from_row(row).to_dict())


@bp.route("/items/<int:iid>", methods=["DELETE"])
def delete_item(iid):
    """删除条目（录入页「跳过」/ 行程页移除）。"""
    db = get_db()
    cur = db.execute("DELETE FROM item WHERE id = ?", (iid,))
    db.commit()
    if cur.rowcount == 0:
        return not_found(f"条目 {iid} 不存在")
    return ok()


@bp.route("/projects/<int:pid>/generate", methods=["POST"])
def generate(pid):
    """生成行程：带 BYOK 大模型配置走 LlmEngine，否则 RuleEngine；LLM 失败自动回退。"""
    row = _project_row(pid)
    if row is None:
        return not_found(f"项目 {pid} 不存在")
    db = get_db()
    req = GenerationRequest.from_project(row)
    data = request.get_json(silent=True) or {}
    llm_cfg = data.get("llm")

    if isinstance(llm_cfg, dict) and llm_cfg.get("api_key"):
        try:
            result = LlmEngine().generate(req, llm_cfg, db=db)
        except Exception as e:
            result = RuleEngine().generate(req, db=db)
            result.suggestions.insert(0, f"AI 规划失败（{e}），已用规则引擎生成")
    else:
        result = RuleEngine().generate(req, db=db)

    _save_tips(pid, result.suggestions, db)
    return ok(_serialize_result(result))


def _save_tips(pid, suggestions, db):
    """把生成建议（含 AI 规划提示）持久化到 project.plan_tips，供行程页展示。"""
    db.execute(
        "UPDATE project SET plan_tips = ? WHERE id = ?",
        (json.dumps(suggestions, ensure_ascii=False), pid),
    )
    db.commit()


@bp.route("/projects/<int:pid>/itinerary", methods=["GET"])
def itinerary(pid):
    """当前行程（已排程条目按天分组）。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    db = get_db()
    rows = db.execute(
        "SELECT * FROM item WHERE project_id = ? AND day IS NOT NULL AND dropped=0 ORDER BY day, order_no",
        (pid,),
    ).fetchall()
    days = {}
    for r in rows:
        it = Item.from_row(r)
        days.setdefault(it.day, []).append(it.to_dict())
    return ok([{"day": d, "items": days[d]} for d in sorted(days)])


# 条目可更新字段（拖拽排序/添加当日/砍单采用撤销 + 修正页编辑）
_ITEM_FIELDS = {
    "name": lambda v: (v or "").strip(),
    "type": lambda v: v,
    "price": lambda v: v,
    "price_source": lambda v: v,
    "lat": lambda v: v,
    "lng": lambda v: v,
    "open_hours": lambda v: v,
    "est_duration": lambda v: v,
    "day": lambda v: v,
    "order_no": lambda v: v,
    "dropped": lambda v: 1 if v else 0,
}


@bp.route("/items/<int:iid>", methods=["PATCH"])
def update_item(iid):
    """更新条目：day/order_no（排序、添加到当日）、dropped（砍单采用/撤销）或编辑字段。"""
    db = get_db()
    row = db.execute("SELECT * FROM item WHERE id = ?", (iid,)).fetchone()
    if row is None:
        return not_found(f"条目 {iid} 不存在")
    data = request.get_json(silent=True) or {}
    fields = {k: fn(data[k]) for k, fn in _ITEM_FIELDS.items() if k in data}
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        db.execute(f"UPDATE item SET {sets} WHERE id = ?", (*fields.values(), iid))
        db.commit()
    row = db.execute("SELECT * FROM item WHERE id = ?", (iid,)).fetchone()
    return ok(Item.from_row(row).to_dict())


@bp.route("/items/<int:iid>/resolve-coord", methods=["POST"])
def resolve_item_coord(iid):
    """按需触发三级坐标查找并写回该条目（行程页「自动获取」按钮）。

    命中本地库或高德成功 → 更新 item.lat/lng 并返回 {lat, lng, source}；
    未命中且无 Key → 3000，前端提示手动完善。
    """
    db = get_db()
    row = db.execute("SELECT * FROM item WHERE id = ?", (iid,)).fetchone()
    if row is None:
        return not_found(f"条目 {iid} 不存在")
    project = db.execute("SELECT city FROM project WHERE id = ?", (row["project_id"],)).fetchone()
    city = project["city"] if project else None

    lat, lng, source = resolve(row["name"], city, db, project_id=row["project_id"])
    if lat is None:
        return fail(CODE_EXT_ERROR, "未获取到坐标：本地库无记录且未配置高德 API Key，请手动完善坐标")

    db.execute("UPDATE item SET lat = ?, lng = ? WHERE id = ?", (lat, lng, iid))
    db.commit()
    return ok({"lat": lat, "lng": lng, "source": source})


@bp.route("/projects/<int:pid>/items/reorder", methods=["POST"])
def reorder_items(pid):
    """批量重排某天条目：body {day: N, item_ids: [id...]}，按数组顺序写入 order_no。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    data = request.get_json(silent=True) or {}
    day = data.get("day")
    ids = data.get("item_ids")
    if not isinstance(ids, list) or not ids:
        return bad_request("缺少 item_ids 数组")
    db = get_db()
    for order, iid in enumerate(ids, start=1):
        db.execute(
            "UPDATE item SET day=?, order_no=? WHERE id=? AND project_id=?",
            (day, order, iid, pid),
        )
    db.commit()
    return ok()


@bp.route("/items/<int:iid>/images", methods=["GET"])
def list_item_images(iid):
    """某条目的记录图片列表。"""
    db = get_db()
    rows = db.execute("SELECT * FROM image WHERE item_id = ? ORDER BY id", (iid,)).fetchall()
    return ok([{"id": r["id"], "url": "/" + r["path"], "caption": r["caption"]} for r in rows])


@bp.route("/items/<int:iid>/images", methods=["POST"])
def upload_item_image(iid):
    """给某条目上传记录图片（multipart file，可选 caption）。"""
    db = get_db()
    if db.execute("SELECT 1 FROM item WHERE id = ?", (iid,)).fetchone() is None:
        return not_found(f"条目 {iid} 不存在")
    f = request.files.get("file")
    if f is None or not f.filename:
        return bad_request("缺少图片文件")
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in _ALLOWED_EXT:
        return bad_request("仅支持 png/jpg/gif/webp 图片")

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"item_{iid}_{int(time.time() * 1000)}{ext}"
    f.save(os.path.join(upload_dir, filename))
    rel = f"static/uploads/{filename}"

    caption = (request.form.get("caption") or "").strip() or None
    cur = db.execute(
        "INSERT INTO image (item_id, path, caption) VALUES (?,?,?)", (iid, rel, caption),
    )
    db.commit()
    return ok({"id": cur.lastrowid, "url": "/" + rel, "caption": caption})
