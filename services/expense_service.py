# -*- coding: utf-8 -*-
"""记账服务：记账 + 分类汇总 + 预估/实际对比。

对应「行程预算与记账」模块：
  - 出行前「行程预算」= 预算服务 compute_budget（按分类：门票/餐饮/交通/住宿）
  - 出行中「记账」= expense 表，按 category 分类
  - 顶部「已花 / 预算」= expense_summary 的 spent_total / estimated_total
"""
from datetime import datetime

from db import get_db
from models import Expense, Item
from services.budget_service import compute_budget

# 记账分类：前四类与预算明细一一对应，「购物」「其他」为补充分类（无预算对照）
CATEGORIES = ["门票", "餐饮", "交通", "住宿", "购物", "其他"]
_BUDGET_KEY = {
    "门票": "ticket_total",
    "餐饮": "food_total",
    "交通": "traffic_total",
    "住宿": "hotel_total",
}


class ProjectNotFoundError(ValueError):
    """项目不存在。"""


class InvalidAmountError(ValueError):
    """金额非法。"""


class InvalidCategoryError(ValueError):
    """分类非法。"""


class ItemNotFoundError(ValueError):
    """关联行程条目不存在。"""


def add_expense(project_id, amount, category=None, item_id=None, note=None, spent_at=None, db=None) -> Expense:
    """新增一笔账单：校验项目/金额/分类/条目后入库，默认记录当前日期。"""
    db = db or get_db()
    if db.execute("SELECT 1 FROM project WHERE id = ?", (project_id,)).fetchone() is None:
        raise ProjectNotFoundError(f"项目 {project_id} 不存在")

    # 金额：必须为正数
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise InvalidAmountError("金额非法，必须是数字")
    if amount <= 0:
        raise InvalidAmountError("金额必须大于 0")

    # 分类：缺省归入「其他」，非法分类报错
    if category is None:
        category = "其他"
    if category not in CATEGORIES:
        raise InvalidCategoryError(f"分类非法，仅支持：{'、'.join(CATEGORIES)}")

    # 可选关联条目：须属于本项目
    if item_id is not None:
        if db.execute(
            "SELECT 1 FROM item WHERE id = ? AND project_id = ?", (item_id, project_id),
        ).fetchone() is None:
            raise ItemNotFoundError(f"关联行程条目 {item_id} 不存在")

    if spent_at is None:
        spent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur = db.execute(
        "INSERT INTO expense (project_id, category, amount, item_id, note, spent_at) VALUES (?,?,?,?,?,?)",
        (project_id, category, amount, item_id, note, spent_at),
    )
    db.commit()
    row = db.execute("SELECT * FROM expense WHERE id = ?", (cur.lastrowid,)).fetchone()
    return Expense.from_row(row)


def list_expenses(project_id, db=None):
    """某项目下所有账单，按时间倒序，附关联条目的 day/name（Day 标签）。"""
    db = db or get_db()
    if db.execute("SELECT 1 FROM project WHERE id = ?", (project_id,)).fetchone() is None:
        raise ProjectNotFoundError(f"项目 {project_id} 不存在")
    rows = db.execute(
        "SELECT e.*, i.day AS item_day, i.name AS item_name "
        "FROM expense e LEFT JOIN item i ON i.id = e.item_id "
        "WHERE e.project_id = ? ORDER BY e.id DESC",
        (project_id,),
    ).fetchall()
    result = []
    for r in rows:
        d = Expense.from_row(r).to_dict()
        d["item_day"] = r["item_day"]
        d["item_name"] = r["item_name"]
        result.append(d)
    return result


def delete_expense(expense_id, db=None) -> bool:
    """删除一笔账单，返回是否删除成功。"""
    db = db or get_db()
    cur = db.execute("DELETE FROM expense WHERE id = ?", (expense_id,))
    db.commit()
    return cur.rowcount > 0


def expense_summary(project_id, db=None) -> dict:
    """已花总额 + 分类汇总 + 预估/实际对比。"""
    db = db or get_db()
    project = db.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise ProjectNotFoundError(f"项目 {project_id} 不存在")

    # 实际花费：按分类汇总
    rows = db.execute(
        "SELECT category, SUM(amount) AS s FROM expense WHERE project_id = ? GROUP BY category",
        (project_id,),
    ).fetchall()
    spent_by_cat = {r["category"]: (r["s"] or 0.0) for r in rows}
    spent_total = sum(spent_by_cat.values())

    # 预估预算：复用预算服务（按分类）
    items = [Item.from_row(r) for r in db.execute(
        "SELECT * FROM item WHERE project_id = ? AND day IS NOT NULL AND dropped=0", (project_id,),
    ).fetchall()]
    budget = compute_budget(items, project["city"], project["days"] or 1, "标准", db,
                            people=project["people"] or 1)

    categories = []
    for cat in CATEGORIES:
        spent = spent_by_cat.get(cat, 0.0)
        key = _BUDGET_KEY.get(cat)
        budget_amt = getattr(budget, key) if key else None
        categories.append({
            "category": cat,
            "budget": budget_amt,
            "spent": spent,
            "diff": (budget_amt - spent) if budget_amt is not None else None,
        })

    estimated = budget.total
    people = project["people"] or 1
    days = project["days"] or 1
    per_person = round(estimated / people, 2)           # 人均预算
    coverage_days = round(spent_total * days / estimated, 2) if estimated else 0.0  # 已花覆盖天数
    over_estimate = max(0.0, spent_total - estimated)   # 超支额（>0 前端出红色警告）

    return {
        "spent_total": spent_total,
        "estimated_total": estimated,
        "user_budget": project["budget"],
        "remaining": estimated - spent_total,
        "per_person": per_person,
        "coverage_days": coverage_days,
        "over_estimate": over_estimate,
        "categories": categories,
    }
