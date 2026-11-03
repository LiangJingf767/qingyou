# -*- coding: utf-8 -*-
"""数据管线自测：提取 → 补全 → 去重合并 → 候选条目集（成都案例）。

运行：cd qiongyou && python -m tests.test_pipeline
"""
import sqlite3

from config import Config
from init_db import init_db   # init_db 会从 data.sql 重建 price_lib，不会丢基础数据
from services.pipeline import run_pipeline


def _fresh_db():
    init_db()   # 清空并重建，保证自测可重复执行（note id 从 1 开始）
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def main():
    conn = _fresh_db()
    conn.executemany(
        "INSERT INTO note (project_id, text, source) VALUES (?,?,?)",
        [
            (2, """【成都3天2晚保姆攻略｜本地人不踩雷✨】
Day1
大熊猫基地，门票55元，7:30开门，游玩3小时，早上去看熊猫最活跃。
宽窄巷子免费，全天开放，逛1.5小时，夜景更好看。""", "小红书"),
            (2, """Day2
武侯祠门票50元，8:30开门，可以玩2小时；锦里古街紧挨着武侯祠，免费，晚上亮灯巨出片。
Day3
杜甫草堂门票50元，9点开园，游玩2小时。
大熊猫基地，门票55元，7:30开门，游玩3小时，一定要早去！人超多，记得提前预约。""", "小红书"),
        ],
    )
    conn.commit()

    items = run_pipeline(2, db=conn)
    by_name = {it.name: it for it in items}

    print("候选条目数:", len(items))
    for it in sorted(items, key=lambda x: x.name):
        print(f"  {it.name} | {it.type} | price={it.price}({it.price_source}) | "
              f"popularity={it.popularity} | source_ids={it.source_ids} | day={it.day}")

    # 断言（item.name 存价格库规范名，如「大熊猫繁育基地」「锦里」）
    dx = by_name["大熊猫繁育基地"]
    assert dx.price == 55.0 and dx.price_source == "用户", "大熊猫基地应为用户价55"
    assert dx.popularity == 2 and set(dx.source_ids.split(",")) == {"1", "2"}, "大熊猫基地应合并两条笔记"
    assert dx.day == 1, "大熊猫基地在Day1"

    kz = by_name["宽窄巷子"]
    assert kz.price == 0.0 and kz.price_source == "用户", "宽窄巷子免费，价格记0"
    assert kz.day == 1

    wh = by_name["武侯祠"]
    assert wh.price == 50.0 and wh.price_source == "用户", "武侯祠门票50"
    assert wh.day == 2

    jl = by_name["锦里"]
    assert jl.price == 0.0 and jl.price_source == "用户", "锦里免费应记0（价格窗口不被引用名截断）"
    assert jl.day == 2

    df = by_name["杜甫草堂"]
    assert df.price == 50.0 and df.price_source == "用户", "杜甫草堂门票50"
    assert df.day == 3

    print("\n[OK] 自测通过")


if __name__ == "__main__":
    main()
