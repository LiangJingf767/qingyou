# -*- coding: utf-8 -*-
"""目的地路由：搜索/列表 + 详情。"""
import os
import time

from flask import Blueprint, current_app, request
from werkzeug.utils import secure_filename

from db import get_db
from response import ok, not_found, bad_request
from services.destination_service import list_destinations, destination_detail, list_attractions, attraction_detail
from services.review_service import list_reviews, add_review

bp = Blueprint("destinations", __name__, url_prefix="/api/v1")

# 允许上传的图片扩展名
_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@bp.route("/destinations", methods=["GET"])
def destinations():
    """目的地列表/搜索，?keyword= 可选（城市名或景点名）。"""
    return ok(list_destinations(keyword=request.args.get("keyword")))


@bp.route("/attractions", methods=["GET"])
def attractions():
    """景点/美食/机位搜索（搜索页直接展示具体条目），?keyword=&type=&limit=。"""
    limit = request.args.get("limit")
    try:
        limit = min(int(limit), 60) if limit else 30
    except ValueError:
        limit = 30
    return ok(list_attractions(
        keyword=request.args.get("keyword"),
        type_=request.args.get("type"),
        limit=limit,
    ))


@bp.route("/attractions/<int:aid>", methods=["GET"])
def attraction(aid):
    """景点详情（搜索页点进去直达，而非城市详情）。"""
    d = attraction_detail(aid)
    if d is None:
        return not_found(f"景点 {aid} 不存在")
    return ok(d)


@bp.route("/attractions/<int:aid>/images", methods=["POST"])
def upload_attraction_image(aid):
    """用户上传景点图片：multipart file 字段，可选 caption 字段。"""
    db = get_db()
    if db.execute("SELECT 1 FROM price_lib WHERE id = ?", (aid,)).fetchone() is None:
        return not_found(f"景点 {aid} 不存在")
    f = request.files.get("file")
    if f is None or not f.filename:
        return bad_request("缺少图片文件")
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in _ALLOWED_EXT:
        return bad_request("仅支持 png/jpg/gif/webp 图片")

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"attr_{aid}_{int(time.time() * 1000)}{ext}"
    f.save(os.path.join(upload_dir, filename))

    caption = (request.form.get("caption") or "").strip() or None
    rel_path = f"static/uploads/{filename}"
    cur = db.execute(
        "INSERT INTO attraction_image (attraction_id, path, caption) VALUES (?,?,?)",
        (aid, rel_path, caption),
    )
    db.commit()
    return ok({"id": cur.lastrowid, "url": "/" + rel_path, "caption": caption})


@bp.route("/attractions/<int:aid>/reviews", methods=["GET"])
def attraction_reviews(aid):
    """某景点评价列表（含均分/条数）。"""
    return ok(list_reviews(aid))


@bp.route("/attractions/<int:aid>/reviews", methods=["POST"])
def post_attraction_review(aid):
    """给景点打分：body {rating: 1-5, comment?}。"""
    data = request.get_json(silent=True) or {}
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        return bad_request("rating 需为 1-5 的整数")
    if rating < 1 or rating > 5:
        return bad_request("rating 需为 1-5 的整数")
    comment = (data.get("comment") or "").strip() or None
    return ok(add_review(aid, rating, comment))


@bp.route("/destinations/<city>", methods=["GET"])
def destination(city):
    """目的地详情。"""
    d = destination_detail(city)
    if d is None:
        return not_found(f"目的地 {city} 不存在")
    return ok(d)
