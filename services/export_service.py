# -*- coding: utf-8 -*-
"""导出服务：图文行程单（Markdown / HTML / 纯文本）。

对应 UC09「输出图文行程单并导出」。三种格式共用同一份数据，接口返回
{filename, format, content}，前端「复制」取 content、「下载」把 content 存为 Blob。
"""
from db import get_db
from models import Item
from services.budget_service import compute_budget, suggest_tradeoffs

_FORMATS = {"md", "txt", "html"}
_EXT = {"md": "md", "txt": "txt", "html": "html", "pdf": "pdf", "png": "png"}


def _gather(project_id, db):
    """取行程单所需数据：project、按天分组的 items、预算、取舍建议。"""
    project = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise ValueError(f"project {project_id} not found")
    items = [Item.from_row(r) for r in db.execute(
        "SELECT * FROM item WHERE project_id = ? AND day IS NOT NULL AND dropped=0 ORDER BY day, order_no",
        (project_id,),
    ).fetchall()]
    days = {}
    for it in items:
        days.setdefault(it.day, []).append(it)
    budget = compute_budget(items, project["city"], project["days"] or 1, "标准", db,
                            people=project["people"] or 1)
    tradeoffs = suggest_tradeoffs(project_id, db=db)
    return project, days, budget, tradeoffs


def render_itinerary(project_id, db=None, fmt="md") -> str:
    """把项目行程渲染成指定格式的图文行程单文本。"""
    db = db or get_db()
    if fmt not in _FORMATS:
        raise ValueError(f"不支持的导出格式 {fmt}")
    project, days, budget, tradeoffs = _gather(project_id, db)

    if fmt == "html":
        return _render_html(project, days, budget, tradeoffs, db)
    if fmt == "txt":
        return _render_txt(project, days, budget, tradeoffs, db)
    return _render_md(project, days, budget, tradeoffs, db)


def render_itinerary_binary(project_id, db=None, fmt="png"):
    """把行程渲染成二进制格式，返回 (bytes, mime)。fmt ∈ {png, pdf}。"""
    from services.export_render import render_long_image, render_pdf
    db = db or get_db()
    project, days, budget, tradeoffs = _gather(project_id, db)
    if fmt == "pdf":
        return render_pdf(project, days, budget, tradeoffs), "application/pdf"
    return render_long_image(project, days, budget, tradeoffs), "image/png"


def build_filename(project, fmt="md") -> str:
    return f"{project['city']}行程单.{_EXT.get(fmt, 'md')}"


# ---- 工具 ----
def _images_for(item_id, db):
    return db.execute(
        "SELECT path, caption FROM image WHERE item_id = ? ORDER BY id", (item_id,),
    ).fetchall()


def _yuan(x):
    if x is None:
        return ""
    if x == 0:
        return "免费"
    return f"{x:.0f} 元"


def _money(x):
    return f"{x:.0f} 元"


def _meta(project):
    parts = []
    if project["start_date"]:
        parts.append(f"出发日期：{project['start_date']}")
    if project["budget"] is not None:
        parts.append(f"总预算：{_money(project['budget'])}")
    return parts


# ---- Markdown ----
def _render_md(project, days, budget, tradeoffs, db):
    L = [f"# {project['city']} {project['days']} 日穷游行程单", ""]
    if _meta(project):
        L.append("　·　".join(_meta(project)))
        L.append("")
    for day in sorted(days):
        L.append(f"## Day {day}")
        for i, it in enumerate(days[day], start=1):
            parts = [it.name]
            if it.type:
                parts.append(it.type)
            if it.price is not None:
                parts.append(_yuan(it.price))
            if it.open_hours:
                parts.append(f"开放 {it.open_hours}")
            if it.est_duration:
                parts.append(f"约 {it.est_duration} 分钟")
            L.append(f"{i}. " + "，".join(parts))
            for path, caption in _images_for(it.id, db):
                L.append(f"   ![{(caption or '')}]({path})")
        L.append("")
    L.append("## 预算明细")
    L.append(f"- 门票：{_money(budget.ticket_total)}")
    L.append(f"- 餐饮：{_money(budget.food_total)}")
    L.append(f"- 交通：{_money(budget.traffic_total)}")
    L.append(f"- 住宿：{_money(budget.hotel_total)}")
    L.append(f"- **合计：{_money(budget.total)}**")
    if tradeoffs:
        L.append("")
        L.append("## 取舍建议")
        for s in tradeoffs:
            L.append(f"- {s}")
    return "\n".join(L)


# ---- 纯文本 ----
def _render_txt(project, days, budget, tradeoffs, db):
    L = [f"{project['city']} {project['days']} 日穷游行程单", "=" * 28]
    if _meta(project):
        L.append(" · ".join(_meta(project)))
    L.append("")
    for day in sorted(days):
        L.append(f"【Day {day}】")
        for i, it in enumerate(days[day], start=1):
            parts = [it.name]
            if it.type:
                parts.append(it.type)
            if it.price is not None:
                parts.append(_yuan(it.price))
            if it.open_hours:
                parts.append(f"开放 {it.open_hours}")
            if it.est_duration:
                parts.append(f"约 {it.est_duration} 分钟")
            L.append(f"  {i}. " + "，".join(parts))
        L.append("")
    L.append("预算明细")
    L.append(f"  门票：{_money(budget.ticket_total)}")
    L.append(f"  餐饮：{_money(budget.food_total)}")
    L.append(f"  交通：{_money(budget.traffic_total)}")
    L.append(f"  住宿：{_money(budget.hotel_total)}")
    L.append(f"  合计：{_money(budget.total)}")
    if tradeoffs:
        L.append("")
        L.append("取舍建议")
        for s in tradeoffs:
            L.append(f"  - {s}")
    return "\n".join(L)


# ---- HTML（独立、移动端友好、可打印）----
_HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>行程单</title>
<style>
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;max-width:600px;margin:0 auto;padding:16px;color:#333}
h1{font-size:20px}
.meta{color:#999;font-size:13px;margin-top:6px}
.day{font-size:17px;margin:20px 0 8px;border-left:4px solid #4caf50;padding-left:8px}
.items{padding-left:4px}
.item{display:flex;padding:8px 0;border-bottom:1px solid #eee}
.idx{width:24px;height:24px;border-radius:50%;background:#4caf50;color:#fff;text-align:center;line-height:24px;font-size:13px;margin-right:10px;flex-shrink:0}
.body{flex:1}
.name{font-weight:600}
.tag{display:inline-block;background:#f0f0f0;border-radius:4px;padding:2px 6px;font-size:12px;margin:4px 4px 0 0}
.tag.price{color:#e65100}
.item img{max-width:100%;border-radius:6px;margin-top:6px}
.budget{background:#f7f7f7;border-radius:8px;padding:12px;margin-top:16px}
.budget div{margin:4px 0}
.total{font-weight:700;color:#e65100}
.advice{margin-top:12px;color:#666;font-size:13px}
</style></head><body>
"""


def _esc(s):
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _render_html(project, days, budget, tradeoffs, db):
    body = []
    body.append("<h1>%s %s 日穷游行程单</h1>" % (_esc(project["city"]), _esc(project["days"])))
    if _meta(project):
        body.append('<div class="meta">%s</div>' % " · ".join(_esc(p) for p in _meta(project)))

    for day in sorted(days):
        body.append('<h2 class="day">Day %s</h2>' % day)
        body.append('<div class="items">')
        for i, it in enumerate(days[day], start=1):
            tags = ""
            if it.type:
                tags += '<span class="tag">%s</span>' % _esc(it.type)
            if it.price is not None:
                tags += '<span class="tag price">%s</span>' % _esc(_yuan(it.price))
            extra = ""
            if it.open_hours:
                extra += '<div class="meta">开放：%s</div>' % _esc(it.open_hours)
            if it.est_duration:
                extra += '<div class="meta">时长：约 %s 分钟</div>' % _esc(it.est_duration)
            imgs = ""
            for path, caption in _images_for(it.id, db):
                imgs += '<img src="%s" alt="%s">' % (_esc(path), _esc(caption or ""))
            body.append(
                '<div class="item"><div class="idx">%d</div>'
                '<div class="body"><div class="name">%s</div>%s%s%s</div></div>'
                % (i, _esc(it.name), tags, extra, imgs)
            )
        body.append("</div>")

    body.append('<div class="budget">')
    body.append("<div>门票：%s</div>" % _money(budget.ticket_total))
    body.append("<div>餐饮：%s</div>" % _money(budget.food_total))
    body.append("<div>交通：%s</div>" % _money(budget.traffic_total))
    body.append("<div>住宿：%s</div>" % _money(budget.hotel_total))
    body.append('<div class="total">合计：%s</div>' % _money(budget.total))
    body.append("</div>")

    if tradeoffs:
        body.append('<div class="advice">%s</div>' % "<br>".join(_esc(s) for s in tradeoffs))

    return _HTML_HEAD + "\n".join(body) + "</body></html>"
