# -*- coding: utf-8 -*-
"""初始化数据库：执行 schema.sql 建表、data.sql 灌入价格库/城市配置，并插入测试数据。

用法：
    python init_db.py

说明：会先删除旧库文件，从零重建（幂等，可重复执行）。
"""
import os
import sqlite3

from config import Config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")
DATA_FILE = os.path.join(BASE_DIR, "data.sql")


def init_db():
    """建表 + 灌入基础数据 + 插入测试数据。"""
    # 删除旧库，保证从零重建（幂等）
    if os.path.exists(Config.DATABASE):
        os.remove(Config.DATABASE)

    conn = sqlite3.connect(Config.DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")

    with open(SCHEMA_FILE, encoding="utf-8") as f:
        conn.executescript(f.read())

    with open(DATA_FILE, encoding="utf-8") as f:
        conn.executescript(f.read())

    _seed(conn)

    conn.commit()
    conn.close()


def _seed(conn):
    """插入 3 条项目测试数据，以及 3 条预算结果。"""
    conn.executemany(
        "INSERT INTO project (city, days, budget, people, start_date, preferences, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("北京", 3, 600.0, 2, "2026-10-26", '["美食", "省钱"]', "editing"),
            ("成都", 2, 500.0, 1, "2026-11-07", '["拍照", "美食"]', "editing"),
            ("上海", 3, 800.0, 3, "2026-11-14", '["文化", "休闲"]', "editing"),
        ],
    )

    # 预算结果（与 3 条项目 1—1 对应，演示外键关系；北京 680 > 600 用于演示预算超支检测）
    conn.executemany(
        "INSERT INTO budget (project_id, ticket_total, food_total, traffic_total, hotel_total, total) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, 150.0, 200.0, 90.0, 240.0, 680.0),
            (2, 100.0, 160.0, 40.0, 160.0, 460.0),
            (3, 180.0, 220.0, 105.0, 260.0, 765.0),
        ],
    )


if __name__ == "__main__":
    init_db()
    print("数据库初始化完成：", Config.DATABASE)
