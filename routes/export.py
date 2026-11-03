# -*- coding: utf-8 -*-
"""导出路由：图文行程单（文本 + PDF/长图）。"""
import base64

from flask import Blueprint, request

from db import get_db
from response import ok, not_found, bad_request
from services.export_service import render_itinerary, render_itinerary_binary, build_filename

bp = Blueprint("export", __name__, url_prefix="/api/v1")

_TEXT_FORMATS = {"md", "txt", "html"}
_BINARY_FORMATS = {"pdf", "png"}
_FORMATS = _TEXT_FORMATS | _BINARY_FORMATS


@bp.route("/projects/<int:pid>/export", methods=["GET"])
def export(pid):
    """?format=md|txt|html|pdf|png。

    文本 → {filename, format, content(字符串)}；
    pdf/png → {filename, format, content(base64), binary: true, mime}。
    """
    fmt = request.args.get("format") or "md"
    if fmt not in _FORMATS:
        return bad_request("format 仅支持 md / txt / html / pdf / png")

    row = get_db().execute("SELECT * FROM project WHERE id = ?", (pid,)).fetchone()
    if row is None:
        return not_found(f"项目 {pid} 不存在")

    if fmt in _BINARY_FORMATS:
        data, mime = render_itinerary_binary(pid, fmt=fmt)
        return ok({
            "filename": build_filename(row, fmt),
            "format": fmt,
            "content": base64.b64encode(data).decode("ascii"),
            "binary": True,
            "mime": mime,
        })

    content = render_itinerary(pid, fmt=fmt)
    return ok({"filename": build_filename(row, fmt), "format": fmt, "content": content})
