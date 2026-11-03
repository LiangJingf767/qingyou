# -*- coding: utf-8 -*-
"""提取服务：纯文本 → 原始实体（价格库词典匹配名称 + 正则抽价格/天数 + 关键词分类）。

规则来源：方案 §4.1 / §5.1(3)。
"""
import bisect
import re
from dataclasses import dataclass
from typing import List, Optional

from db import get_db
from services.normalize import core_name, normalize_name

# 价格正则：数字 + 元/块/¥/￥，或 门票/人均/¥ 后跟数字
_PRICE_NUM_RE = re.compile(
    r"(?:门票|人均|¥|￥)\s*(\d+(?:\.\d+)?)"
    r"|(\d+(?:\.\d+)?)\s*(?:元|块|¥|￥)"
)
_FREE_RE = re.compile(r"免费")
_DAY_RE = re.compile(r"(?:第\s*(\d+)\s*天|Day\s*(\d+))", re.IGNORECASE)

# 类型关键词（价格库未命中类型时的兜底分类）
_KEYWORDS = {
    "景点": ["门票", "景区", "公园", "博物馆"],
    "美食": ["吃", "餐厅", "人均", "小吃", "美食"],
    "机位": ["机位", "拍照", "打卡", "角度"],
}


@dataclass
class RawEntity:
    name: str
    type: Optional[str] = None
    price: Optional[float] = None
    price_source: Optional[str] = None   # 文本提取到价格时记 "用户"
    day: Optional[int] = None
    note: Optional[str] = None           # 大模型提取的地点备注（上下文提示）
    source_note_id: Optional[int] = None

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def classify_type(segment: str) -> Optional[str]:
    """关键词分类：命中最多的一类胜出。"""
    scores = {t: sum(segment.count(k) for k in kws) for t, kws in _KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def _price_occurrences(text: str):
    """返回 [(位置, 价格), ...]，「免费」计为 0。"""
    occ = []
    for m in _PRICE_NUM_RE.finditer(text):
        val = next((g for g in m.groups() if g is not None), None)
        if val:
            occ.append((m.start(), float(val)))
    for m in _FREE_RE.finditer(text):
        occ.append((m.start(), 0.0))
    occ.sort()
    return occ


def _day_marks(text: str):
    """返回 [(位置, 第N天), ...]。"""
    marks = []
    for m in _DAY_RE.finditer(text):
        val = int(next(g for g in m.groups() if g is not None))
        marks.append((m.start(), val))
    marks.sort()
    return marks


def _fallback_candidates(text: str, matched_ranges):
    """行级启发式：识别价格库未收录、但文本中「名称 + 触发词」明确出现的名称。

    只提取「触发词前、2-12 字、不含价格数字」的片段，保守起见每段最多一个。
    返回 [(pos, name, type), ...]，供主流程与字典命中结果一起做价格/天数归属。
    """
    _TRIGGERS = ("门票", "免费", "开放时间", "开放", "游玩", "逛", "打卡", "拍照",
                 "吃", "餐厅", "美食", "博物馆", "公园", "景区", "古城", "老街")
    cands = []
    for m in re.finditer(r"[^\n。；;]+", text):
        seg, s0 = m.group(), m.start()
        if any(lo <= s0 < hi or (s0 <= lo < s0 + len(seg)) for lo, hi in matched_ranges):
            continue
        pre = re.match(r"^(?:第\s*\d+\s*天|Day\s*\d+)\s*[:：、.\s]*", seg, re.IGNORECASE)
        offset = pre.end() if pre else 0
        body = seg[offset:]
        hit = None
        for kw in _TRIGGERS:
            k = body.find(kw)
            if k > 0 and (hit is None or k < hit[0]):
                hit = (k, kw)
        if not hit:
            continue
        name = re.sub(r"[\d\.元块¥￥/]", "", body[:hit[0]])
        name = name.strip(" ，。、；;：:·—()（）的与和及去到了在从往")
        if not (2 <= len(name) <= 12):
            continue
        typ = classify_type(body) or classify_type(name)
        abs_pos = s0 + offset + body.find(name)
        cands.append((abs_pos, name, typ))
    return cands


def extract_text(text: str, city: str, db=None) -> List[RawEntity]:
    """文本 → 原始实体列表（按 (规范化名, 类型) 去重；价格归属紧随其后的名称）。"""
    db = db or get_db()
    rows = db.execute(
        "SELECT name, type FROM price_lib WHERE city = ? ORDER BY LENGTH(name) DESC",
        (city,),
    ).fetchall()

    # 名称出现位置：依次尝试 全名 → 归一化名 → 核心名（简称）
    name_occ = []   # (pos, name, type, norm)
    matched_ranges = []   # (start, end) 已命中的字符区间
    for row in rows:
        name, typ = row["name"], row["type"]
        forms = []
        for f in (name, normalize_name(name), core_name(name)):
            if f and len(f) >= 2 and f not in forms:
                forms.append(f)
        matched = next((f for f in forms if f in text), None)
        if matched is None:
            continue
        norm = normalize_name(name)
        start = 0
        while True:
            pos = text.find(matched, start)
            if pos < 0:
                break
            name_occ.append((pos, name, typ, norm))
            matched_ranges.append((pos, pos + len(matched)))
            start = pos + max(1, len(matched))
    name_occ.sort()

    # 去重：每个 (规范化名, 类型) 只保留首次出现，作为价格窗口边界，
    # 避免「锦里古街紧挨着武侯祠，免费」中第二个「武侯祠」把锦里的价格窗口截断。
    distinct = []
    seen = set()
    for occ in name_occ:
        key = (occ[3], occ[2])
        if key in seen:
            continue
        seen.add(key)
        distinct.append(occ)

    # 价格库未收录名称的兜底识别（扩大「能识别」的覆盖面）
    for pos, name, typ in _fallback_candidates(text, matched_ranges):
        key = (normalize_name(name), typ)
        if key in seen:
            continue
        seen.add(key)
        distinct.append((pos, name, typ, normalize_name(name)))
    distinct.sort()

    price_occ = _price_occurrences(text)
    price_positions = [p for p, _ in price_occ]
    price_values = [v for _, v in price_occ]
    day_marks = _day_marks(text)

    entities = []
    for i, (pos, name, typ, norm) in enumerate(distinct):
        # 价格窗口：本名称到下一个「不同」名称之间
        hi = distinct[i + 1][0] if i + 1 < len(distinct) else len(text) + 1
        idx = bisect.bisect_left(price_positions, pos)
        price = price_values[idx] if idx < len(price_positions) and price_positions[idx] < hi else None

        # 天数：名称前最近的「第N天」
        day = None
        for mp, mv in day_marks:
            if mp <= pos:
                day = mv
            else:
                break

        entities.append(RawEntity(
            name=name,
            type=typ or classify_type(text[max(0, pos - 5):pos + len(name) + 10]),
            price=price,
            price_source="用户" if price is not None else None,
            day=day,
        ))
    return entities
