# -*- coding: utf-8 -*-
"""REST API 自测：统一响应格式 + 核心业务流程端点。

运行：cd qiongyou && python -m tests.test_api
"""
from init_db import init_db
from app import app


def main():
    init_db()
    app.config["TESTING"] = True
    c = app.test_client()

    # 1. 统一响应格式：ping
    r = c.get("/api/v1/ping")
    body = r.get_json()
    assert set(body) == {"code", "message", "data"}
    assert body["code"] == 0

    # 2. 创建项目（preferences 传数组，start_date 用于闭馆日）
    r = c.post("/api/v1/projects", json={
        "city": "成都", "days": 3, "budget": 100,
        "start_date": "2026-10-19", "preferences": ["拍照", "美食"],
    })
    body = r.get_json()
    assert body["code"] == 0, body
    pid = body["data"]["id"]
    assert body["data"]["start_date"] == "2026-10-19"
    assert body["data"]["preferences"] == ["拍照", "美食"]

    # 3. 录入笔记
    r = c.post(f"/api/v1/projects/{pid}/notes", json={
        "text": "Day1 大熊猫基地，门票55元。\n"
                "Day2 武侯祠门票50元；锦里古街免费。\n"
                "Day3 杜甫草堂门票50元。",
        "source": "小红书",
    })
    assert r.get_json()["code"] == 0

    # 4. 跑管线 → 候选条目
    r = c.post(f"/api/v1/projects/{pid}/pipeline")
    body = r.get_json()
    assert body["code"] == 0
    assert body["data"]["count"] >= 4

    # 5. 生成行程（含冲突 + 建议）
    r = c.post(f"/api/v1/projects/{pid}/generate")
    body = r.get_json()
    assert body["code"] == 0, body
    data = body["data"]
    assert len(data["days"]) == 3
    assert any(conf["type"] == "预算超支" for conf in data["conflicts"])

    # 6. 行程查询
    r = c.get(f"/api/v1/projects/{pid}/itinerary")
    assert r.get_json()["code"] == 0 and len(r.get_json()["data"]) == 3

    # 7. 预算核算（成都 3 天：门票155 餐饮135 交通75 住宿150 = 515）
    r = c.get(f"/api/v1/projects/{pid}/budget")
    body = r.get_json()
    assert body["code"] == 0
    assert body["data"]["budget"]["total"] == 515.0
    assert any("可优先砍" in s for s in body["data"]["suggestions"])

    # 8. 冲突检测
    r = c.get(f"/api/v1/projects/{pid}/conflicts")
    body = r.get_json()
    assert body["code"] == 0
    assert any(c["type"] == "预算超支" for c in body["data"])

    # 9. 错误也走统一格式：缺参 → 1000，不存在 → 2004
    assert c.post("/api/v1/projects", json={}).get_json()["code"] == 1000
    assert c.get("/api/v1/projects/999999").get_json()["code"] == 2004

    print("\n[OK] REST API 自测通过")


if __name__ == "__main__":
    main()
