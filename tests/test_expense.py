# -*- coding: utf-8 -*-
"""记账模块自测（行程预算与记账）：已花/预算 + 分类汇总 + 预估/实际对比 + 异常。

运行：cd qiongyou && python -m tests.test_expense
"""
from init_db import init_db
from app import app


def main():
    init_db()
    app.config["TESTING"] = True
    c = app.test_client()

    # 建项目 + 录笔记 + 管线 + 生成（成都 3 天，预估 515 元）
    r = c.post("/api/v1/projects", json={
        "city": "成都", "days": 3, "budget": 100,
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

    # 1. 初始汇总：已花 0，预估 515
    s = c.get(f"/api/v1/projects/{pid}/expenses/summary").get_json()
    assert s["code"] == 0
    assert s["data"]["spent_total"] == 0.0
    assert s["data"]["estimated_total"] == 515.0
    assert s["data"]["remaining"] == 515.0
    assert s["data"]["user_budget"] == 100.0
    assert s["data"]["per_person"] == 515.0      # 人均预算 = 预估/同行人数(默认1)
    assert s["data"]["coverage_days"] == 0.0     # 已花0，覆盖0天
    assert s["data"]["over_estimate"] == 0.0
    by_cat = {x["category"]: x for x in s["data"]["categories"]}
    assert by_cat["门票"]["budget"] == 155.0
    assert by_cat["其他"]["budget"] is None
    assert by_cat["购物"]["budget"] is None      # 购物为无预算对照分类

    # 2. 记账两笔
    r = c.post(f"/api/v1/projects/{pid}/expenses", json={"amount": 200, "category": "门票", "note": "熊猫基地门票"})
    body = r.get_json()
    assert body["code"] == 0, body
    assert body["data"]["amount"] == 200.0
    assert body["data"]["spent_at"], "应自动记录记账日期"

    r = c.post(f"/api/v1/projects/{pid}/expenses", json={"amount": 80, "category": "餐饮"})
    assert r.get_json()["code"] == 0

    # 3. 汇总：已花 280，门票超支、餐饮有余
    s = c.get(f"/api/v1/projects/{pid}/expenses/summary").get_json()["data"]
    assert s["spent_total"] == 280.0
    assert s["remaining"] == 235.0
    by_cat = {x["category"]: x for x in s["categories"]}
    assert by_cat["门票"]["spent"] == 200.0 and by_cat["门票"]["diff"] == -45.0
    assert by_cat["餐饮"]["spent"] == 80.0 and by_cat["餐饮"]["diff"] == 55.0
    assert by_cat["交通"]["spent"] == 0.0 and by_cat["交通"]["diff"] == 75.0

    # 4. 关联行程条目（取真实 item id）
    item_id = c.get(f"/api/v1/projects/{pid}/items").get_json()["data"][0]["id"]
    r = c.post(f"/api/v1/projects/{pid}/expenses", json={"amount": 50, "category": "交通", "item_id": item_id})
    body = r.get_json()
    assert body["code"] == 0 and body["data"]["item_id"] == item_id

    # 5. 异常分支：金额非法 / 分类非法 / 项目不存在 / 条目不存在
    assert c.post(f"/api/v1/projects/{pid}/expenses", json={"amount": 0}).get_json()["code"] == 1000
    assert c.post(f"/api/v1/projects/{pid}/expenses", json={"amount": -5}).get_json()["code"] == 1000
    assert c.post(f"/api/v1/projects/{pid}/expenses", json={"amount": "abc"}).get_json()["code"] == 1000
    assert c.post(f"/api/v1/projects/{pid}/expenses", json={"amount": 10, "category": "娱乐"}).get_json()["code"] == 1000
    assert c.post("/api/v1/projects/999999/expenses", json={"amount": 10}).get_json()["code"] == 2004
    assert c.post(f"/api/v1/projects/{pid}/expenses", json={"amount": 10, "item_id": 999999}).get_json()["code"] == 2004

    # 6. 列表 + 删除
    lst = c.get(f"/api/v1/projects/{pid}/expenses").get_json()["data"]
    assert len(lst) == 3
    eid = lst[0]["id"]
    assert c.delete(f"/api/v1/expenses/{eid}").get_json()["code"] == 0
    assert len(c.get(f"/api/v1/projects/{pid}/expenses").get_json()["data"]) == 2
    assert c.delete(f"/api/v1/expenses/{eid}").get_json()["code"] == 2004  # 重复删除

    # 7. 购物分类已纳入（无预算对照，仅累计已花）
    assert c.post(f"/api/v1/projects/{pid}/expenses", json={"amount": 30, "category": "购物"}).get_json()["code"] == 0
    s7 = c.get(f"/api/v1/projects/{pid}/expenses/summary").get_json()["data"]
    by7 = {x["category"]: x for x in s7["categories"]}
    assert by7["购物"]["budget"] is None and by7["购物"]["spent"] == 30.0

    print("\n[OK] 记账模块自测通过")


if __name__ == "__main__":
    main()
