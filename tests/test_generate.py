# -*- coding: utf-8 -*-
"""生成引擎自测：候选条目 → RuleEngine 生成按天行程。

运行：cd qiongyou && python -m tests.test_generate
"""
import sqlite3

from config import Config
from init_db import init_db
from services.pipeline import run_pipeline
from engine import RuleEngine, GenerationRequest


def _fresh_db():
    init_db()
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
    run_pipeline(2, db=conn)   # 先产候选条目

    # 成都种子项目 days=2，改成 3 天以匹配笔记；预算先置空，验证无冲突
    conn.execute("UPDATE project SET days = 3, budget = NULL WHERE id = 2")
    proj = conn.execute("SELECT * FROM project WHERE id = 2").fetchone()
    result = RuleEngine().generate(GenerationRequest.from_project(proj), db=conn)

    for dp in result.days:
        line = " | ".join(f"{it.name}#{it.order_no}(p{it.popularity})" for it in dp.items) or "(空)"
        print(f"Day{dp.day}: {line}")
    print("冲突:", [(c.type, c.message) for c in result.conflicts])
    print("建议:", result.suggestions)

    # 断言：3 天、天内顺序（景点内按热门度降序）
    d1 = {it.name: it for it in result.days[0].items}
    d2 = {it.name: it for it in result.days[1].items}
    d3 = {it.name: it for it in result.days[2].items}
    assert len(result.days) == 3
    assert d1["大熊猫繁育基地"].order_no == 1 and d1["宽窄巷子"].order_no == 2
    assert d2["武侯祠"].order_no == 1 and d2["锦里"].order_no == 2
    assert d3["杜甫草堂"].order_no == 1
    assert not result.conflicts, "预算未设时不应有冲突"

    # 预算超支场景：压低预算后应检测到超支
    conn.execute("UPDATE project SET budget = 100 WHERE id = 2")
    proj = conn.execute("SELECT * FROM project WHERE id = 2").fetchone()
    result2 = RuleEngine().generate(GenerationRequest.from_project(proj), db=conn)
    assert any(c.type == "预算超支" for c in result2.conflicts)
    print("\n预算100时的冲突:", [(c.type, c.message) for c in result2.conflicts])
    print("建议:", result2.suggestions)

    print("\n[OK] 生成引擎自测通过")


if __name__ == "__main__":
    main()
