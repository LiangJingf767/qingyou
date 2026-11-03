# -*- coding: utf-8 -*-
"""冲突检测（§4.6）+ 预算服务（§4.5）自测。

运行：cd qiongyou && python -m tests.test_conflict_budget
"""
import datetime
import sqlite3

from config import Config
from init_db import init_db
from services.pipeline import run_pipeline
from engine import RuleEngine, GenerationRequest
from services.budget_service import calc_budget, suggest_tradeoffs
from services.conflict_service import detect_conflicts


def _fresh_db():
    init_db()
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def main():
    conn = _fresh_db()

    # ---- 项目2（成都）跑管线 + 生成 ----
    conn.executemany(
        "INSERT INTO note (project_id, text, source) VALUES (?,?,?)",
        [
            (2, """Day1
大熊猫基地，门票55元，7:30开门，游玩3小时。
宽窄巷子免费，全天开放，逛1.5小时。""", "小红书"),
            (2, """Day2
武侯祠门票50元，8:30开门；锦里古街紧挨着武侯祠，免费。
Day3
杜甫草堂门票50元，9点开园。""", "小红书"),
        ],
    )
    conn.commit()
    run_pipeline(2, db=conn)
    conn.execute("UPDATE project SET days = 3, budget = 100 WHERE id = 2")
    proj = conn.execute("SELECT * FROM project WHERE id = 2").fetchone()
    RuleEngine().generate(GenerationRequest.from_project(proj), db=conn)

    # ---- §4.5 预算公式（成都 transit25/hostel50/meal45，3 天）----
    b = calc_budget(2, db=conn)
    print(f"预算: 门票{b.ticket_total:.1f} 餐饮{b.food_total:.1f} "
          f"交通{b.traffic_total:.1f} 住宿{b.hotel_total:.1f} 合计{b.total:.1f}")
    assert b.ticket_total == 155.0   # 55 + 50 + 50（宽窄巷子/锦里免费）
    assert b.food_total == 135.0     # 无美食 → 3 天 × 45
    assert b.traffic_total == 75.0   # 3 × 25
    assert b.hotel_total == 150.0    # 3 × 50
    assert b.total == 515.0

    # 预算已落库（档位测试会覆盖，先在此校验标准档）
    row = conn.execute("SELECT total FROM budget WHERE project_id = 2").fetchone()
    assert row is not None and row["total"] == b.total

    # 档位：省钱 < 标准 < 舒适
    cheap = calc_budget(2, tier="省钱", db=conn)
    comfort = calc_budget(2, tier="舒适", db=conn)
    assert cheap.total < b.total < comfort.total

    # ---- §4.6 预算超支（100 元预算 vs 515 元）----
    conflicts = detect_conflicts(2, db=conn)
    print("冲突:", [(c.type, c.message) for c in conflicts])
    assert any(c.type == "预算超支" for c in conflicts)

    # ---- 取舍建议 ----
    sugg = suggest_tradeoffs(2, db=conn)
    print("建议:", sugg)
    assert any("可优先砍" in s for s in sugg)

    # ---- 闭馆日 / 距离过远（项目1 北京，手工造数，不干扰项目2）----
    conn.execute("UPDATE project SET budget = NULL WHERE id = 1")
    conn.execute("DELETE FROM item WHERE project_id = 1")
    conn.execute(
        "INSERT INTO item (project_id, name, type, day, order_no, open_hours, lat, lng, est_duration) "
        "VALUES (1,'故宫博物院','景点',1,1,'08:30-17:00(周一闭馆)',39.9163,116.3972,120)")
    conn.execute(
        "INSERT INTO item (project_id, name, type, day, order_no, open_hours, lat, lng, est_duration) "
        "VALUES (1,'八达岭长城','景点',1,2,'07:30-17:30',40.3539,116.0025,120)")
    conn.commit()

    # 找一个周一作为出发日，写进 project.start_date；detect_conflicts 不传参时自动读取
    d = datetime.date(2026, 10, 19)
    while d.weekday() != 0:
        d += datetime.timedelta(days=1)
    conn.execute("UPDATE project SET start_date = ? WHERE id = 1", (d.isoformat(),))
    conn.commit()
    conflicts2 = detect_conflicts(1, db=conn)   # 不传 start_date，走 project.start_date
    print("造数后冲突:", [(c.type, c.message) for c in conflicts2])
    assert any(c.type == "闭馆日" and "故宫" in c.message for c in conflicts2), "应检测到闭馆日"
    assert any(c.type == "距离过远" for c in conflicts2), "应检测到距离过远"

    print("\n[OK] 冲突检测 + 预算服务自测通过")


if __name__ == "__main__":
    main()
