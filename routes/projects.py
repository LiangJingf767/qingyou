# -*- coding: utf-8 -*-
"""项目与笔记路由（资源录入层）。"""
import json
import os
import time

from flask import Blueprint, current_app, request

from db import get_db
from models import Project, Note
from response import ok, bad_request, not_found, fail, CODE_BIZ_ERROR
from services.pipeline import append_note

bp = Blueprint("projects", __name__, url_prefix="/api/v1")

_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _project_row(pid):
    return get_db().execute("SELECT * FROM project WHERE id = ?", (pid,)).fetchone()


def _dump_preferences(p):
    """偏好可为 list/dict，入库前序列化为 JSON 文本。"""
    return json.dumps(p, ensure_ascii=False) if isinstance(p, (list, dict)) else p


def _project_dict(row):
    """项目 → 字典；preferences / plan_tips 反序列化，便于前端直接使用。"""
    d = Project.from_row(row).to_dict()
    for k in ("preferences", "plan_tips"):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except (TypeError, ValueError):
                pass
    return d


@bp.route("/projects", methods=["GET"])
def list_projects():
    db = get_db()
    rows = db.execute("SELECT * FROM project ORDER BY id DESC").fetchall()
    return ok([_project_dict(r) for r in rows])


@bp.route("/projects", methods=["POST"])
def create_project():
    data = request.get_json(silent=True) or {}
    city = (data.get("city") or "").strip()
    if not city:
        return bad_request("缺少参数 city")

    db = get_db()
    cur = db.execute(
        "INSERT INTO project (city, days, budget, people, start_date, preferences) VALUES (?,?,?,?,?,?)",
        (city, int(data.get("days") or 1), data.get("budget"), int(data.get("people") or 1),
         data.get("start_date"), _dump_preferences(data.get("preferences"))),
    )
    db.commit()
    row = db.execute("SELECT * FROM project WHERE id = ?", (cur.lastrowid,)).fetchone()
    return ok(_project_dict(row))


@bp.route("/projects/<int:pid>", methods=["GET"])
def get_project(pid):
    row = _project_row(pid)
    if row is None:
        return not_found(f"项目 {pid} 不存在")
    return ok(_project_dict(row))


@bp.route("/projects/<int:pid>", methods=["PUT"])
def update_project(pid):
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    data = request.get_json(silent=True) or {}

    # 允许更新的字段及类型转换
    mapping = {
        "city": lambda v: (v or "").strip(),
        "days": int,
        "people": int,
        "budget": lambda v: v,
        "start_date": lambda v: v,
        "preferences": _dump_preferences,
        "status": lambda v: v,
    }
    fields = {k: fn(data[k]) for k, fn in mapping.items() if k in data}

    db = get_db()
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        db.execute(f"UPDATE project SET {sets} WHERE id = ?", (*fields.values(), pid))
        db.commit()
    row = db.execute("SELECT * FROM project WHERE id = ?", (pid,)).fetchone()
    return ok(_project_dict(row))


@bp.route("/projects/<int:pid>", methods=["DELETE"])
def delete_project(pid):
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    db = get_db()
    db.execute("DELETE FROM project WHERE id = ?", (pid,))
    db.commit()
    return ok()


@bp.route("/projects/<int:pid>/cover", methods=["POST"])
def upload_cover(pid):
    """上传行程封面（multipart file 字段），写回 project.cover。"""
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    f = request.files.get("file")
    if f is None or not f.filename:
        return bad_request("缺少图片文件")
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in _ALLOWED_EXT:
        return bad_request("仅支持 png/jpg/gif/webp 图片")

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"cover_{pid}_{int(time.time() * 1000)}{ext}"
    f.save(os.path.join(upload_dir, filename))
    rel = f"static/uploads/{filename}"

    db = get_db()
    db.execute("UPDATE project SET cover = ? WHERE id = ?", (rel, pid))
    db.commit()
    return ok({"url": "/" + rel})


# ---- 笔记 ----
@bp.route("/projects/<int:pid>/notes", methods=["GET"])
def list_notes(pid):
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    db = get_db()
    rows = db.execute("SELECT * FROM note WHERE project_id = ? ORDER BY id", (pid,)).fetchall()
    return ok([Note.from_row(r).to_dict() for r in rows])


@bp.route("/projects/<int:pid>/notes", methods=["POST"])
def create_note(pid):
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return bad_request("缺少参数 text")
    source = data.get("source") or "手动"

    db = get_db()
    cur = db.execute(
        "INSERT INTO note (project_id, text, source) VALUES (?,?,?)", (pid, text, source),
    )
    db.commit()
    row = db.execute("SELECT * FROM note WHERE id = ?", (cur.lastrowid,)).fetchone()
    return ok(Note.from_row(row).to_dict())


@bp.route("/projects/<int:pid>/notes/append", methods=["POST"])
def append_note_route(pid):
    """追加一篇攻略：提取地点并与已有条目增量合并（重复热度+1 / 新地点入候选）。

    body 可带 {llm: cfg} 用大模型提取；缺省或失败时降级正则提取。
    """
    if _project_row(pid) is None:
        return not_found(f"项目 {pid} 不存在")
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return bad_request("缺少参数 text")
    source = data.get("source") or "小红书"
    try:
        result = append_note(pid, text, source, llm_config=data.get("llm"))
    except ValueError as e:
        return fail(CODE_BIZ_ERROR, str(e))
    return ok(result)


@bp.route("/notes/<int:nid>", methods=["DELETE"])
def delete_note(nid):
    db = get_db()
    cur = db.execute("DELETE FROM note WHERE id = ?", (nid,))
    db.commit()
    if cur.rowcount == 0:
        return not_found(f"笔记 {nid} 不存在")
    return ok()
