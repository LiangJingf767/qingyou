# -*- coding: utf-8 -*-
"""记账路由：新增/列表/删除账单 + 汇总对比。"""
from flask import Blueprint, request

from response import ok, not_found, bad_request
from services.expense_service import (
    add_expense, list_expenses, delete_expense, expense_summary,
    ProjectNotFoundError, InvalidAmountError, InvalidCategoryError, ItemNotFoundError,
)

bp = Blueprint("expense", __name__, url_prefix="/api/v1")


@bp.route("/projects/<int:pid>/expenses", methods=["POST"])
def create_expense(pid):
    """新增账单。body: amount(必填), category?, item_id?, note?, spent_at?"""
    data = request.get_json(silent=True) or {}
    try:
        exp = add_expense(
            pid,
            amount=data.get("amount"),
            category=data.get("category"),
            item_id=data.get("item_id"),
            note=data.get("note"),
            spent_at=data.get("spent_at"),
        )
    except ProjectNotFoundError as e:
        return not_found(str(e))
    except ItemNotFoundError as e:
        return not_found(str(e))
    except (InvalidAmountError, InvalidCategoryError) as e:
        return bad_request(str(e))
    return ok(exp.to_dict())


@bp.route("/projects/<int:pid>/expenses", methods=["GET"])
def list_project_expenses(pid):
    """账单列表。"""
    try:
        return ok(list_expenses(pid))
    except ProjectNotFoundError as e:
        return not_found(str(e))


@bp.route("/projects/<int:pid>/expenses/summary", methods=["GET"])
def get_summary(pid):
    """已花/预算 + 分类汇总 + 预估/实际对比。"""
    try:
        return ok(expense_summary(pid))
    except ProjectNotFoundError as e:
        return not_found(str(e))


@bp.route("/expenses/<int:eid>", methods=["DELETE"])
def remove_expense(eid):
    """删除账单。"""
    if not delete_expense(eid):
        return not_found(f"账单 {eid} 不存在")
    return ok()
