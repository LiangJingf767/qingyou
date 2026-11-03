# -*- coding: utf-8 -*-
"""高德地图接入自测：坐标解析 / 服务封装 / 坐标回填 / 路由错误映射（全程 mock，不访问外网）。

运行：cd qiongyou && python -m tests.test_amap
"""
import sqlite3

import services.amap_service as svc
from config import Config
from init_db import init_db
from app import app


class _FakeResp:
    """伪造 urlopen 的响应（上下文管理器 + read）。"""

    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._payload.encode("utf-8")


def _boom(*a, **k):
    raise svc.AmapError("boom", "10001")


def main():
    # 1. 坐标字符串解析
    assert svc._split_lnglat("116.397029,39.917839") == (116.397029, 39.917839)
    assert svc._split_lnglat("") == (None, None)
    assert svc._split_lnglat("bad") == (None, None)

    # 2. _get 非成功状态 → AmapError（mock urlopen 走真实 _get 校验逻辑）
    svc.urllib.request.urlopen = lambda req, timeout=None: _FakeResp(
        '{"status":"0","infocode":"10001","info":"INVALID_USER_KEY"}')
    try:
        svc._get("geocode/geo", {"address": "x"})
        assert False, "应抛 AmapError"
    except svc.AmapError as e:
        assert e.infocode == "10001"

    # 3. 地理编码解析（mock _get 返回成功数据）
    svc._get = lambda path, params: {
        "status": "1", "infocode": "10000",
        "geocodes": [{"location": "104.138176,30.740573",
                      "formatted_address": "四川省成都市成华区", "level": "兴趣点"}],
    }
    g = svc.geocode("成都大熊猫繁育研究基地", city="成都")
    assert g[0]["lng"] == 104.138176 and g[0]["lat"] == 30.740573

    # 4. POI 搜索解析
    svc._get = lambda path, params: {
        "status": "1", "infocode": "10000",
        "pois": [{"id": "B001C7WE5S", "name": "成都大熊猫繁育研究基地",
                  "location": "104.138176,30.740573", "address": "熊猫大道1375号",
                  "type": "风景名胜", "typecode": "110202", "tel": "028-83510033",
                  "biz_ext": {"rating": "4.8", "open_time": "07:30-17:00"}}],
    }
    p = svc.search_poi("大熊猫", city="成都")
    assert p[0]["name"].startswith("成都大熊猫") and p[0]["rating"] == "4.8"

    # 5. 驾车规划解析
    svc._get = lambda path, params: {
        "status": "1", "infocode": "10000",
        "route": {"origin": "116.397029,39.917839", "destination": "116.398972,39.905242",
                  "paths": [{"distance": "4223", "duration": "744",
                             "steps": [{"polyline": "116.395,39.917;116.393,39.917"}]}]},
    }
    r = svc.driving("116.397029,39.917839", "116.398972,39.905242")
    assert r["distance"] == 4223 and r["duration"] == 744

    # 6. 坐标回填写库（mock geocode，不访问外网）
    init_db()
    svc.geocode = lambda name, city=None: [
        {"lng": 104.1, "lat": 30.7, "formatted_address": "x", "level": "兴趣点"}]
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    ok, skip = svc.backfill_price_lib_coords(city="成都", limit=3, db=conn, sleep=0)
    assert ok == 3 and skip == 0, (ok, skip)
    n = conn.execute(
        "SELECT COUNT(*) c FROM price_lib WHERE city='成都' AND lat IS NOT NULL").fetchone()["c"]
    assert n >= 3
    conn.close()

    # 7. 路由：缺参数 1000；高德异常 → 3000
    init_db()
    app.config["TESTING"] = True
    c = app.test_client()
    assert c.get("/api/v1/map/geocode").get_json()["code"] == 1000
    assert c.get("/api/v1/map/directions?origin=1,1").get_json()["code"] == 1000

    import routes.map as mr
    mr.geocode = _boom
    assert c.get("/api/v1/map/geocode?address=x").get_json()["code"] == 3000

    print("\n[OK] 高德地图接入自测通过")


if __name__ == "__main__":
    main()
