# -*- coding: utf-8 -*-
"""目的地服务：搜索/列表 + 详情 + 景点条目搜索（⑨⑩）。

数据来源：
  - city_config：城市日均（交通/住宿/餐饮）
  - price_lib：城市下的景点/美食/机位
  - review：用户评分（均分/条数），用于「必去景点」客观排序
无真实来源的字段（介绍/预订）返回占位 null / []，前端据此渲染占位容器。
"""
from db import get_db
from services.review_service import list_reviews

# 评分子查询（复用：每条 price_lib 附带 review 均分与条数）
_RATING_SQL = (
    "(SELECT ROUND(AVG(rating), 1) FROM review r WHERE r.attraction_id = p.id) AS rating, "
    "(SELECT COUNT(*) FROM review r WHERE r.attraction_id = p.id) AS review_count"
)


def _lib_dict(r):
    """price_lib 行 → 前端友好字典（含评分）。"""
    return {
        "id": r["id"],
        "name": r["name"],
        "type": r["type"],
        "price": r["price"],
        "open_hours": r["open_hours"],
        "source": r["source"],
        "lat": r["lat"],        # 地图打点用；未回填时为 None
        "lng": r["lng"],
        "rating": r["rating"] if "rating" in r.keys() else None,
        "review_count": r["review_count"] if "review_count" in r.keys() else 0,
    }


def list_destinations(keyword=None, db=None):
    """目的地列表/搜索：按城市聚合，返回人均日均与三类条目计数。"""
    db = db or get_db()
    if keyword:
        kw = f"%{keyword.strip()}%"
        rows = db.execute(
            "SELECT * FROM city_config c "
            "WHERE c.city LIKE ? "
            "   OR c.city IN (SELECT DISTINCT city FROM price_lib WHERE name LIKE ?) "
            "ORDER BY c.city",
            (kw, kw),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM city_config ORDER BY city").fetchall()

    out = []
    for r in rows:
        city = r["city"]
        counts = db.execute(
            "SELECT type, COUNT(*) AS n FROM price_lib WHERE city=? GROUP BY type", (city,),
        ).fetchall()
        tc = {c["type"]: c["n"] for c in counts}
        daily = (r["transit_avg"] or 0) + (r["meal_avg"] or 0) + (r["hostel_avg"] or 0)
        out.append({
            "city": city,
            "daily_estimate": round(daily, 2),   # 人均日均预估
            "attractions": tc.get("景点", 0),
            "foods": tc.get("美食", 0),
            "spots": tc.get("机位", 0),
        })
    return out


def list_attractions(keyword=None, type_=None, limit=30, db=None):
    """景点/美食/机位搜索：返回具体条目（含城市、类型、价格、用户评分）。"""
    db = db or get_db()
    sql = f"SELECT p.*, {_RATING_SQL} FROM price_lib p WHERE 1=1"
    args = []
    if keyword:
        kw = f"%{keyword.strip()}%"
        sql += " AND (p.name LIKE ? OR p.city LIKE ?)"
        args += [kw, kw]
    if type_:
        sql += " AND p.type = ?"
        args.append(type_)
    sql += " ORDER BY (p.lat IS NULL), p.id LIMIT ?"
    args.append(limit)
    rows = db.execute(sql, args).fetchall()
    return [{
        "id": r["id"],
        "name": r["name"],
        "city": r["city"],
        "type": r["type"],
        "price": r["price"],
        "open_hours": r["open_hours"],
        "lat": r["lat"],
        "lng": r["lng"],
        "rating": r["rating"],
        "review_count": r["review_count"],
    } for r in rows]


def destination_detail(city, db=None):
    """目的地详情：三项指标 + 必去景点/美食/机位清单（按用户评分排序）。不存在返回 None。"""
    db = db or get_db()
    cfg = db.execute("SELECT * FROM city_config WHERE city=?", (city,)).fetchone()
    if cfg is None:
        return None
    rows = db.execute(
        f"SELECT p.*, {_RATING_SQL} FROM price_lib p WHERE p.city=? ORDER BY p.id",
        (city,),
    ).fetchall()
    daily = (cfg["transit_avg"] or 0) + (cfg["meal_avg"] or 0) + (cfg["hostel_avg"] or 0)

    # 「必去景点」按用户均分降序（无评分排后），再按名称，体现客观推荐而非主观预设
    attractions = sorted(
        (_lib_dict(r) for r in rows if r["type"] == "景点"),
        key=lambda x: (x["rating"] is None, -(x["rating"] or 0), x["name"]),
    )

    city_ratings = [r["rating"] for r in rows if r["type"] == "景点" and r["rating"] is not None]
    city_avg = round(sum(city_ratings) / len(city_ratings), 1) if city_ratings else None

    return {
        "city": city,
        "metrics": {
            "rating": city_avg,                     # 城市综合评分 = 各景点均分的均值
            "daily_estimate": round(daily, 2),      # 人均日均预估
            "route_days": 3,                        # 建议游玩天数，占位
        },
        "transit_avg": cfg["transit_avg"],
        "hostel_avg": cfg["hostel_avg"],
        "meal_avg": cfg["meal_avg"],
        "attractions": attractions,
        "foods": [_lib_dict(r) for r in rows if r["type"] == "美食"],
        "spots": [_lib_dict(r) for r in rows if r["type"] == "机位"],
        "intro": None,                              # 介绍无真实数据，占位
        "booking": [],                              # 预订信息无真实数据，占位
    }


def attraction_detail(aid, db=None):
    """景点详情：基本信息 + 用户评价 + 用户上传图片。不存在返回 None。"""
    db = db or get_db()
    r = db.execute(
        f"SELECT p.*, {_RATING_SQL} FROM price_lib p WHERE p.id = ?", (aid,),
    ).fetchone()
    if r is None:
        return None
    imgs = db.execute(
        "SELECT id, path, caption FROM attraction_image WHERE attraction_id = ? ORDER BY id DESC",
        (aid,),
    ).fetchall()
    return {
        "id": r["id"],
        "name": r["name"],
        "city": r["city"],
        "type": r["type"],
        "price": r["price"],
        "open_hours": r["open_hours"],
        "source": r["source"],
        "lat": r["lat"],
        "lng": r["lng"],
        "rating": r["rating"],
        "review_count": r["review_count"],
        "reviews": list_reviews(aid, db),
        "images": [{"id": i["id"], "url": "/" + i["path"], "caption": i["caption"]} for i in imgs],
    }
