# -*- coding: utf-8 -*-
"""评价服务：景点用户评分（1-5 星 + 可选评论），供「必去景点」客观排序。"""
from db import get_db


def _rating(attraction_id, db):
    row = db.execute(
        "SELECT COUNT(*) AS n, AVG(rating) AS avg FROM review WHERE attraction_id = ?",
        (attraction_id,),
    ).fetchone()
    n = row["n"] or 0
    avg = round(row["avg"], 1) if row["avg"] is not None else None
    return n, avg


def rating_for(attraction_id, db=None):
    """返回 (review_count, avg_rating)。"""
    db = db or get_db()
    return _rating(attraction_id, db)


def list_reviews(attraction_id, db=None):
    """返回该景点的评价列表（含均分与条数）。"""
    db = db or get_db()
    n, avg = _rating(attraction_id, db)
    rows = db.execute(
        "SELECT * FROM review WHERE attraction_id = ? ORDER BY created_at DESC, id DESC",
        (attraction_id,),
    ).fetchall()
    reviews = [{
        "id": r["id"],
        "rating": r["rating"],
        "comment": r["comment"],
        "created_at": r["created_at"],
    } for r in rows]
    return {"count": n, "avg": avg, "reviews": reviews}


def add_review(attraction_id, rating, comment=None, db=None):
    """新增一条评价，返回该景点最新统计。"""
    db = db or get_db()
    cur = db.execute(
        "INSERT INTO review (attraction_id, rating, comment) VALUES (?,?,?)",
        (attraction_id, rating, comment),
    )
    db.commit()
    return list_reviews(attraction_id, db)
