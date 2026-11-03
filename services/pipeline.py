# -*- coding: utf-8 -*-
"""数据管线：多篇笔记 → 提取 → 补全 → 去重合并 → 候选条目集（写库）。

对应方案 §2.3 管线前半段。
"""
from typing import List, Tuple

from db import get_db
from models import Item
from services.extract import extract_text
from services.enrich import enrich
from services.dedup import dedup, _similar, _merge
from services.llm_extract import extract_locations


def _extract_entities(text, city, db, llm_config):
    """单篇文本 → 原始实体。配置了 BYOK 且调用成功走大模型提取，否则降级正则。"""
    if llm_config and (llm_config or {}).get("api_key"):
        try:
            return list(extract_locations(text, llm_config))
        except Exception:
            pass  # 大模型失败 → 降级正则
    return extract_text(text, city, db)


def build_candidate_items(city: str, texts: List[Tuple[int, str]], db=None, llm_config=None, project_id=None) -> List[Item]:
    """纯计算：texts 为 [(note_id, text), ...] → 候选条目集（不写库）。"""
    db = db or get_db()
    entities = []
    for note_id, text in texts:
        for e in _extract_entities(text, city, db, llm_config):
            e.source_note_id = note_id
            entities.append(e)
    return dedup(enrich(entities, city, db, project_id=project_id))


def run_pipeline(project_id: int, db=None, llm_config=None) -> List[Item]:
    """读取项目 note → 跑管线 → 写回 item 表，返回候选条目集。"""
    db = db or get_db()
    project = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise ValueError(f"project {project_id} not found")

    notes = db.execute("SELECT * FROM note WHERE project_id = ?", (project_id,)).fetchall()
    items = build_candidate_items(project["city"], [(n["id"], n["text"]) for n in notes], db,
                                  llm_config=llm_config, project_id=project_id)

    # 候选集全量重建：清空该项目旧条目，再写回
    db.execute("DELETE FROM item WHERE project_id = ?", (project_id,))
    for it in items:
        it.project_id = project_id
        db.execute(
            "INSERT INTO item (project_id, name, type, price, price_source, lat, lng, "
            "open_hours, est_duration, day, order_no, popularity, source_ids, note) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (it.project_id, it.name, it.type, it.price, it.price_source, it.lat, it.lng,
             it.open_hours, it.est_duration, it.day, it.order_no, it.popularity, it.source_ids,
             it.note),
        )
    db.commit()
    return items


def append_note(project_id: int, text: str, source: str = "小红书", db=None, llm_config=None) -> dict:
    """增量追加一篇攻略：写入 note，提取地点并与已有条目合并（重复则热度 +1，新地点入候选）。

    与 run_pipeline 的全量重建不同，这里不动已有条目的 day/order_no/dropped，
    只做「重复 → popularity+1 + 来源合并」或「新地点 → 插入为候选（day=NULL）」。
    返回 {"added": 新地点数, "merged": 合并重复数, "note_id": ...}。
    """
    db = db or get_db()
    project = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise ValueError(f"project {project_id} not found")
    city = project["city"]

    cur = db.execute(
        "INSERT INTO note (project_id, text, source) VALUES (?,?,?)", (project_id, text, source),
    )
    note_id = cur.lastrowid

    entities = []
    for e in _extract_entities(text, city, db, llm_config):
        e.source_note_id = note_id
        entities.append(e)
    new_items = enrich(entities, city, db, project_id=project_id)

    existing = [Item.from_row(r) for r in db.execute(
        "SELECT * FROM item WHERE project_id = ?", (project_id,),
    ).fetchall()]

    added = merged = 0
    for it in new_items:
        target = next(
            (m for m in existing if m.type == it.type and _similar(m.name, it.name)),
            None,
        )
        if target is None:
            db.execute(
                "INSERT INTO item (project_id, name, type, price, price_source, lat, lng, "
                "open_hours, est_duration, day, order_no, popularity, source_ids, note) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (project_id, it.name, it.type, it.price, it.price_source, it.lat, it.lng,
                 it.open_hours, it.est_duration, it.day, it.order_no, 1, str(note_id), it.note),
            )
            added += 1
        else:
            _merge(target, it)
            db.execute(
                "UPDATE item SET popularity=?, source_ids=?, price=?, price_source=?, "
                "open_hours=?, lat=?, lng=?, est_duration=?, type=?, day=?, note=COALESCE(note, ?) WHERE id=?",
                (target.popularity, target.source_ids, target.price, target.price_source,
                 target.open_hours, target.lat, target.lng, target.est_duration,
                 target.type, target.day, it.note, target.id),
            )
            merged += 1

    db.commit()
    return {"added": added, "merged": merged, "note_id": note_id}
