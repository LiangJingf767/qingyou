# -*- coding: utf-8 -*-
"""条目写操作自测：拖拽排序 / 添加到当日 + 砍单采用/撤销 + 批量重排。

运行：cd qiongyou && python -m tests.test_items
"""
from init_db import init_db
from app import app


def main():
    init_db()
    app.config["TESTING"] = True
    c = app.test_client()

    # 建项目 + 笔记 + 管线 + 生成（成都 3 天，4 个条目全排上，无裁剪）
    r = c.post("/api/v1/projects", json={
        "city": "成都", "days": 3, "budget": 100, "people": 2,
        "start_date": "2026-10-19", "preferences": ["拍照", "美食"],
    })
    pid = r.get_json()["data"]["id"]
    c.post(f"/api/v1/projects/{pid}/notes", json={
        "text": "Day1 大熊猫基地，门票55元。\n"
                "Day2 武侯祠门票50元；锦里古街免费。\n"
                "Day3 杜甫草堂门票50元。",
        "source": "小红书",
    })
    c.post(f"/api/v1/projects/{pid}/pipeline")
    c.post(f"/api/v1/projects/{pid}/generate")

    items = c.get(f"/api/v1/projects/{pid}/items").get_json()["data"]
    assert len(items) >= 4, items
    A, B = items[0], items[1]

    # 1. 添加到当日 / 排序：PATCH day + order_no
    r = c.patch(f"/api/v1/items/{B['id']}", json={"day": 1, "order_no": 9})
    body = r.get_json()
    assert body["code"] == 0, body
    assert body["data"]["day"] == 1 and body["data"]["order_no"] == 9

    # 2. 砍单采用：dropped=1 → 不再出现在 itinerary
    r = c.patch(f"/api/v1/items/{A['id']}", json={"dropped": 1})
    assert r.get_json()["code"] == 0 and r.get_json()["data"]["dropped"] == 1
    names = {it["name"] for d in c.get(f"/api/v1/projects/{pid}/itinerary").get_json()["data"]
             for it in d["items"]}
    assert A["name"] not in names, "砍单后不应出现在行程"

    # 3. 撤销：dropped=0 → 恢复
    assert c.patch(f"/api/v1/items/{A['id']}", json={"dropped": 0}).get_json()["data"]["dropped"] == 0
    names = {it["name"] for d in c.get(f"/api/v1/projects/{pid}/itinerary").get_json()["data"]
             for it in d["items"]}
    assert A["name"] in names, "撤销后应恢复"

    # 4. 批量重排：前两个条目按序放入 Day1
    ids = [it["id"] for it in items[:2]]
    assert c.post(f"/api/v1/projects/{pid}/items/reorder",
                  json={"day": 1, "item_ids": ids}).get_json()["code"] == 0
    # 缺 item_ids → 参数错误
    assert c.post(f"/api/v1/projects/{pid}/items/reorder",
                  json={"day": 1}).get_json()["code"] == 1000

    # 5. 异常：条目不存在
    assert c.patch("/api/v1/items/999999", json={"day": 1}).get_json()["code"] == 2004

    print("\n[OK] 条目写操作自测通过")


if __name__ == "__main__":
    main()
