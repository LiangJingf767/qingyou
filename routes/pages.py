# -*- coding: utf-8 -*-
"""前端页面路由：移动端 B/S 页面（对应《高保真原型设计说明书》①—⑩）。"""
from flask import Blueprint, redirect, render_template
from markupsafe import Markup

bp = Blueprint("pages", __name__)

# 路径 → 模板（无后缀 = 页面名.html）
_PAGES = {
    "home": "home.html",
    "new-plan": "new-plan.html",
    "capture": "capture.html",
    "edit-item": "edit-item.html",
    "itinerary": "itinerary.html",
    "budget": "budget.html",
    "export": "export.html",
    "settings": "settings.html",
    "search": "search.html",
    "detail": "detail.html",
    "attraction": "attraction.html",
}

# 线性图标（stroke=currentColor），与 static/js/api.js 的 icon() 保持同源
_ICON_PATHS = {
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "wallet": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "back": '<path d="m15 5-7 7 7 7"/>',
    "export": '<path d="M12 3v12"/><path d="m7 8 5 5 5-5"/><path d="M4 21h16"/>',
    "map": '<path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "pin": '<path d="M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "drag": '<path d="M9 5h.01M9 12h.01M9 19h.01M15 5h.01M15 12h.01M15 19h.01"/>',
    "edit": '<path d="M4 20h4L20 8l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    "check": '<path d="m5 12 5 5L20 7"/>',
    "chevR": '<path d="m9 5 7 7-7 7"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.5"/><path d="m3 17 5-5 4 4 3-3 6 6"/>',
    "doc": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "star": '<path d="m12 3 2.7 5.6 6.3.9-4.5 4.4 1 6.1L12 17l-5.5 3 1-6.1L3 9.5l6.3-.9z"/>',
    "heart": '<path d="M12 20s-7-4.5-9-9a5 5 0 0 1 9-3 5 5 0 0 1 9 3c-2 4.5-9 9-9 9z"/>',
    "camera": '<rect x="3" y="7" width="18" height="13" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8 7l1.5-3h5L16 7"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/>',
}


def icon_svg(name, size=22):
    """服务端图标：返回 inline SVG（已标记 safe，避免被 Jinja 转义）。"""
    d = _ICON_PATHS.get(name, _ICON_PATHS["pin"])
    svg = (
        '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{d}</svg>'
    ).format(s=size, d=d)
    return Markup(svg)


@bp.route("/")
def index():
    return redirect("/home")


@bp.route("/<path:name>")
def page(name):
    """按文件名直出页面；未知路径交 404。"""
    tpl = _PAGES.get(name)
    if tpl is None:
        from flask import abort
        abort(404)
    return render_template(tpl)
