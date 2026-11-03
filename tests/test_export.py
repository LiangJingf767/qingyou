# -*- coding: utf-8 -*-
"""导出服务自测（UC09 图文行程单）：Markdown / 纯文本 / HTML。

运行：cd qiongyou && python -m tests.test_export
"""
from init_db import init_db
from app import app


def main():
    init_db()
    app.config["TESTING"] = True
    c = app.test_client()

    # 建项目 + 录笔记 + 管线 + 生成
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

    # 1. Markdown
    r = c.get(f"/api/v1/projects/{pid}/export?format=md")
    body = r.get_json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["filename"] == "成都行程单.md"
    assert "# 成都" in data["content"]
    assert "Day 1" in data["content"]
    assert "大熊猫繁育基地" in data["content"]
    assert "预算明细" in data["content"]
    assert "可优先砍" in data["content"]   # 超支建议
    print("--- Markdown ---\n" + data["content"] + "\n")

    # 2. 纯文本
    r = c.get(f"/api/v1/projects/{pid}/export?format=txt")
    body = r.get_json()
    assert body["code"] == 0
    txt = body["data"]["content"]
    assert body["data"]["filename"] == "成都行程单.txt"
    assert "【Day 1】" in txt and "合计" in txt

    # 3. HTML
    r = c.get(f"/api/v1/projects/{pid}/export?format=html")
    body = r.get_json()
    assert body["code"] == 0
    html = body["data"]["content"]
    assert "<html" in html and 'class="day"' in html
    assert "大熊猫繁育基地" in html
    assert body["data"]["filename"] == "成都行程单.html"

    # 4. 非法格式 / 项目不存在
    assert c.get(f"/api/v1/projects/{pid}/export?format=pdf").get_json()["code"] == 1000
    assert c.get("/api/v1/projects/999999/export").get_json()["code"] == 2004

    print("\n[OK] 导出服务自测通过")


if __name__ == "__main__":
    main()
