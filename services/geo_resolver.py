# -*- coding: utf-8 -*-
"""坐标三级查找 + 自动缓存。

resolve(name, city, db, project_id=None) -> (lat, lng, source)

  第一级（本地）：先查 price_lib（全局共享缓存），再查本项目 item（已有条目复用），
                 命中即用，不发网络请求（省额度、速度快）；
  第二级（动态）：配置了高德 Web 服务 Key 时，调用地理编码（带 city 防同名异地）；
  第三级（缓存）：高德成功后把坐标写回 price_lib，之后同地点直接走本地，库越用越全。
  兜底：未配置 Key 且本地无坐标 → 返回 (None, None, None)，由前端引导手动补充。

坐标写入 item 表由调用方完成（enrich 给 Item 赋值后由管线写库；resolve-coord
接口显式 UPDATE item），本模块只负责 price_lib 这一「全局、可固化」缓存。
"""
from config import Config
from services.amap_service import AmapError, geocode
from services.normalize import normalize_name

SOURCE_PRICE_LIB = "price_lib"
SOURCE_ITEM = "item"
SOURCE_AMAP = "amap"


def _has_key():
    """是否配置了可用的高德 Web 服务 Key。"""
    return bool(Config.AMAP_KEY) and Config.AMAP_KEY != "YOUR_AMAP_KEY"


def resolve(name, city, db, project_id=None):
    """按三级策略解析坐标，返回 (lat, lng, source)；source 为 None 表示未获取到。"""
    if not name:
        return None, None, None

    # 第一级：本地缓存
    row = db.execute(
        "SELECT lat, lng FROM price_lib WHERE city = ? AND name = ? "
        "AND lat IS NOT NULL AND lng IS NOT NULL LIMIT 1",
        (city, name),
    ).fetchone()
    if row:
        return row["lat"], row["lng"], SOURCE_PRICE_LIB

    if project_id is not None:
        nm = normalize_name(name)
        rows = db.execute(
            "SELECT name, lat, lng FROM item WHERE project_id = ? "
            "AND lat IS NOT NULL AND lng IS NOT NULL",
            (project_id,),
        ).fetchall()
        for r in rows:
            if normalize_name(r["name"]) == nm:
                return r["lat"], r["lng"], SOURCE_ITEM

    # 第二级：高德地理编码
    if _has_key():
        try:
            geo = geocode(name, city=city)
        except AmapError:
            geo = []
        if geo and geo[0].get("lng") is not None:
            lat, lng = geo[0]["lat"], geo[0]["lng"]
            _cache(name, city, lat, lng, db)   # 第三级：写回本地缓存
            return lat, lng, SOURCE_AMAP

    # 兜底：未配置 Key 且本地无坐标
    return None, None, None


def _cache(name, city, lat, lng, db):
    """把高德返回的坐标写回 price_lib（仅补齐库中已有但缺坐标的条目，不新增行）。"""
    row = db.execute(
        "SELECT id, lat, lng FROM price_lib WHERE city = ? AND name = ? LIMIT 1",
        (city, name),
    ).fetchone()
    if row is None or (row["lat"] is not None and row["lng"] is not None):
        return
    db.execute("UPDATE price_lib SET lat = ?, lng = ? WHERE id = ?", (lat, lng, row["id"]))
