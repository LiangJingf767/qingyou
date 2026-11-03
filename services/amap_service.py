# -*- coding: utf-8 -*-
"""高德开放平台 Web服务 API 封装（后端 Key，走服务端）。

能力：
  - geocode        地理编码（地址/名称 → 坐标）
  - regeo          逆地理编码（坐标 → 结构化地址）
  - search_poi     POI 关键字搜索（place/text）
  - input_tips     输入提示（assistant/inputtips，目的地搜索框联想）
  - driving        驾车路径规划（行程页点对点距离/时长/轨迹）

坐标体系：高德 Web服务 与 JS API 均返回 GCJ-02（火星坐标），前后端一致，无需转换。

限流：个人开发者 Key 约 3 QPS、日配额有限，批量回填（backfill_price_lib_coords）
已内置 sleep 与 limit，请勿并发调用。
"""
import json
import time
import urllib.parse
import urllib.request

from config import Config
from db import get_db

_BASE = "https://restapi.amap.com/v3"
_TIMEOUT = 8


class AmapError(Exception):
    """高德服务返回异常（网络 / 业务失败）。"""

    def __init__(self, message, infocode=None):
        super().__init__(message)
        self.infocode = infocode


def _get(path, params):
    """GET 高德接口并解析 JSON；status != "1" 或 infocode != "10000" 抛 AmapError。"""
    params = dict(params)
    params["key"] = Config.AMAP_KEY
    url = f"{_BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "qiongyou/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
    except Exception as e:  # 网络异常 / 超时
        raise AmapError(f"高德接口请求失败：{e}") from e
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise AmapError("高德接口返回非 JSON") from e
    if str(data.get("status")) != "1" or str(data.get("infocode")) != "10000":
        raise AmapError(
            f"高德接口错误：{data.get('info') or data.get('infocode')}",
            infocode=data.get("infocode"),
        )
    return data


def _split_lnglat(s):
    """'lng,lat' → (lng: float, lat: float)；异常返回 (None, None)。"""
    if not s:
        return None, None
    try:
        lng, lat = (float(x) for x in str(s).split(",", 1))
        return lng, lat
    except (ValueError, TypeError):
        return None, None


def geocode(address, city=None):
    """地理编码：地址/名称 → 坐标。返回 [{lng, lat, formatted_address, level}]，无结果返回 []。"""
    params = {"address": address}
    if city:
        params["city"] = city
    data = _get("geocode/geo", params)
    out = []
    for g in data.get("geocodes") or []:
        lng, lat = _split_lnglat(g.get("location"))
        out.append({
            "lng": lng,
            "lat": lat,
            "formatted_address": g.get("formatted_address"),
            "level": g.get("level"),
        })
    return out


def regeo(lng, lat):
    """逆地理编码：坐标 → 结构化地址。返回 {formatted_address, province, city, district, adcode}。"""
    data = _get("geocode/regeo", {"location": f"{lng},{lat}", "extensions": "base"})
    rc = (data.get("regeocode") or {}).get("addressComponent") or {}
    return {
        "formatted_address": (data.get("regeocode") or {}).get("formatted_address"),
        "province": rc.get("province"),
        "city": rc.get("city"),
        "district": rc.get("district"),
        "adcode": rc.get("adcode"),
    }


def search_poi(keywords, city=None, types=None, offset=10, page=1):
    """POI 关键字搜索。返回 [{id, name, lng, lat, address, type, typecode, tel, rating, open_time}]。"""
    params = {"keywords": keywords, "offset": offset, "page": page, "extensions": "all"}
    if city:
        params["city"] = city
    if types:
        params["types"] = types
    data = _get("place/text", params)
    out = []
    for p in data.get("pois") or []:
        lng, lat = _split_lnglat(p.get("location"))
        biz = p.get("biz_ext") or {}
        out.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "lng": lng,
            "lat": lat,
            "address": p.get("address"),
            "type": p.get("type"),
            "typecode": p.get("typecode"),
            "tel": p.get("tel"),
            "rating": biz.get("rating"),
            "open_time": biz.get("open_time"),
        })
    return out


def input_tips(keywords, city=None):
    """输入提示（目的地搜索框联想）。返回 [{id, name, lng, lat, district, address}]。"""
    params = {"keywords": keywords}
    if city:
        params["city"] = city
    data = _get("assistant/inputtips", params)
    out = []
    for t in data.get("tips") or []:
        lng, lat = _split_lnglat(t.get("location"))
        out.append({
            "id": t.get("id"),
            "name": t.get("name"),
            "lng": lng,
            "lat": lat,
            "district": t.get("district"),
            "address": t.get("address"),
        })
    return out


def driving(origin, destination):
    """驾车路径规划。origin/destination 为 'lng,lat' 字符串或 (lng, lat) 元组。

    返回 {origin, destination, distance(米), duration(秒), polyline}；无路径返回 None。
    """
    def _fmt(x):
        if isinstance(x, (tuple, list)):
            return f"{x[0]},{x[1]}"
        return str(x)

    data = _get("direction/driving", {
        "origin": _fmt(origin),
        "destination": _fmt(destination),
        "strategy": 2,  # 少拥堵
    })
    route = data.get("route") or {}
    paths = route.get("paths") or []
    if not paths:
        return None
    p = paths[0]
    polyline = ";".join(s.get("polyline", "") for s in p.get("steps", []))
    return {
        "origin": route.get("origin"),
        "destination": route.get("destination"),
        "distance": int(p.get("distance") or 0),
        "duration": int(p.get("duration") or 0),
        "polyline": polyline,
    }


def backfill_price_lib_coords(city=None, limit=None, db=None, sleep=0.12):
    """为 price_lib 中缺失坐标的条目做地理编码回填，写回 lat/lng。

    返回 (成功数, 跳过数)。无结果/失败条目保持 NULL，可重复执行直至补齐。
    """
    db = db or get_db()
    sql = "SELECT id, city, name FROM price_lib WHERE (lat IS NULL OR lng IS NULL)"
    args = []
    if city:
        sql += " AND city = ?"
        args.append(city)
    sql += " ORDER BY id"
    if limit:
        sql += " LIMIT ?"
        args.append(limit)
    rows = db.execute(sql, args).fetchall()

    ok = skip = 0
    for r in rows:
        try:
            geo = geocode(r["name"], city=r["city"])
        except AmapError:
            skip += 1
            continue
        if not geo or geo[0]["lng"] is None:
            skip += 1
            continue
        g = geo[0]
        db.execute("UPDATE price_lib SET lat=?, lng=? WHERE id=?", (g["lat"], g["lng"], r["id"]))
        ok += 1
        if sleep:
            time.sleep(sleep)
    db.commit()
    return ok, skip
