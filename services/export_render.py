# -*- coding: utf-8 -*-
"""导出图片渲染：把行程单渲染成 PNG 长图 / 多页 PDF。

用 PIL + Windows 中文字体（Microsoft YaHei / 黑体）离线绘制，不依赖浏览器或
外部 HTML→PDF 工具。文本格式（md/txt/html）仍在 export_service.py 里。
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont

# A4 @ ~150dpi，保证中文字体清晰
PAGE_W = 1240
PAGE_H = 1754
MARGIN = 80
LINE_H = 52

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",  # 微软雅黑 粗体（标题）
    "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑（正文）
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]


def _font_path():
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    # 兜底：无中文字体时用 PIL 默认（会画不出汉字，但至少不崩）
    return None


def _make_fonts():
    base = _font_path()
    if base is None:
        return None
    def f(size):
        try:
            return ImageFont.truetype(base, size)
        except Exception:
            return ImageFont.load_default()
    return {
        "title": f(52),
        "h2": f(40),
        "body": f(30),
        "small": f(26),
    }


def _wrap(draw, text, font, max_w):
    """按像素宽度把 text 折成多行。"""
    lines = []
    for raw in str(text).split("\n"):
        if raw == "":
            lines.append("")
            continue
        cur = ""
        for ch in raw:
            if draw.textlength(cur + ch, font=font) <= max_w:
                cur += ch
            else:
                if cur:
                    lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    return lines


class _Canvas:
    """分页画布：写文本行，超页高自动换页（用于 PDF）；长图模式不换页。"""

    def __init__(self, fonts, page_h):
        self.fonts = fonts
        self.page_h = page_h
        self.pages = []
        self._new_page()

    def _new_page(self):
        h = self.page_h or 20000   # 长图模式（page_h=0）用大画布，最后裁剪
        img = Image.new("RGB", (PAGE_W, h), "white")
        self.img = img
        self.draw = ImageDraw.Draw(img)
        self.y = MARGIN
        self.pages.append(img)

    def text(self, s, font_key, color="#222", gap=LINE_H, indent=0):
        font = self.fonts[font_key]
        max_w = PAGE_W - MARGIN * 2 - indent
        lines = _wrap(self.draw, s, font, max_w)
        for ln in lines:
            if self.page_h and self.y + gap > self.page_h - MARGIN:
                self._new_page()
            self.draw.text((MARGIN + indent, self.y), ln, font=font, fill=color)
            self.y += gap
        return self.y

    def line(self, color="#E0E0E0", gap=12):
        if self.page_h and self.y + gap > self.page_h - MARGIN:
            self._new_page()
        self.draw.line([(MARGIN, self.y), (PAGE_W - MARGIN, self.y)], fill=color, width=2)
        self.y += gap


def _yuan(x):
    if x is None:
        return ""
    if x == 0:
        return "免费"
    return f"{x:.0f} 元"


def _money(x):
    return f"{x:.0f} 元"


def _render(canvas, project, days, budget, tradeoffs):
    city = project["city"] or ""
    canvas.text(f"{city} {project['days']} 日穷游行程单", "title", color="#2F6B52", gap=64)

    meta = []
    if project["start_date"]:
        meta.append(f"出发日期：{project['start_date']}")
    if project["budget"] is not None:
        meta.append(f"总预算：{_money(project['budget'])}")
    if meta:
        canvas.text(" · ".join(meta), "small", color="#888", gap=30)
    canvas.line()

    for day in sorted(days):
        canvas.text(f"Day {day}", "h2", color="#2F6B52", gap=56)
        for i, it in enumerate(days[day], start=1):
            parts = [it.name]
            if it.type:
                parts.append(it.type)
            if it.price is not None:
                parts.append(_yuan(it.price))
            canvas.text(f"{i}. " + "　".join(parts), "body", color="#222")
            sub = []
            if it.open_hours:
                sub.append("开放 " + str(it.open_hours))
            if it.est_duration:
                sub.append("约 " + str(it.est_duration) + " 分钟")
            if sub:
                canvas.text("　　" + "　".join(sub), "small", color="#888", gap=40)
        canvas.line(gap=24)

    canvas.text("预算明细", "h2", color="#2F6B52", gap=56)
    for k, v in (("门票", budget.ticket_total), ("餐饮", budget.food_total),
                 ("交通", budget.traffic_total), ("住宿", budget.hotel_total)):
        canvas.text(f"{k}：{_money(v)}", "body", color="#444")
    canvas.text(f"合计：{_money(budget.total)}", "body", color="#D9574F", gap=56)

    if tradeoffs:
        canvas.text("取舍建议", "h2", color="#2F6B52", gap=56)
        for s in tradeoffs:
            canvas.text("· " + s, "small", color="#666", gap=42)


def _gather_data(project_id, db):
    from services.export_service import _gather
    return _gather(project_id, db)


def render_long_image(project, days, budget, tradeoffs) -> bytes:
    """渲染成一张长图（PNG），返回字节。"""
    fonts = _make_fonts()
    canvas = _Canvas(fonts, page_h=0)  # page_h=0 → 不换页
    _render(canvas, project, days, budget, tradeoffs)
    # 裁剪到实际内容高度（去白边）
    height = min(canvas.y + MARGIN, 30000)
    img = canvas.pages[0].crop((0, 0, PAGE_W, height))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_pdf(project, days, budget, tradeoffs) -> bytes:
    """渲染成多页 PDF（每页 A4），返回字节。"""
    fonts = _make_fonts()
    canvas = _Canvas(fonts, page_h=PAGE_H)
    _render(canvas, project, days, budget, tradeoffs)
    buf = io.BytesIO()
    first, *rest = canvas.pages
    first.save(buf, format="PDF", save_all=True, append_images=rest, resolution=150)
    return buf.getvalue()
