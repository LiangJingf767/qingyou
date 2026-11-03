# -*- coding: utf-8 -*-
"""目的地搜索/详情自测（⑨目的地搜索、⑩目的地详情）。

运行：cd qiongyou && python -m tests.test_destinations
"""
from init_db import init_db
from app import app


def main():
    init_db()
    app.config["TESTING"] = True
    c = app.test_client()

    # 1. 列表：成都 daily_estimate = 25 + 50 + 45 = 120
    d = c.get("/api/v1/destinations").get_json()["data"]
    chengdu = next(x for x in d if x["city"] == "成都")
    assert chengdu["daily_estimate"] == 120.0, chengdu

    # 2. 关键字搜索：城市名 / 景点名都能命中成都
    for kw in ["成都", "大熊猫"]:
        d = c.get("/api/v1/destinations", query_string={"keyword": kw}).get_json()["data"]
        assert any(x["city"] == "成都" for x in d), kw

    # 3. 详情：含景点清单，命中价格库“大熊猫基地”，且带 lat/lng 字段（回填后填充）
    d = c.get("/api/v1/destinations/成都").get_json()["data"]
    assert d["city"] == "成都" and d["metrics"]["daily_estimate"] == 120.0
    assert any("大熊猫" in a["name"] for a in d["attractions"])
    assert all("lat" in a and "lng" in a for a in d["attractions"])

    # 4. 不存在 → 2004
    assert c.get("/api/v1/destinations/火星").get_json()["code"] == 2004

    print("\n[OK] 目的地搜索/详情自测通过")


if __name__ == "__main__":
    main()
