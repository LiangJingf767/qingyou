# -*- coding: utf-8 -*-
"""服务层：提取 / 补全 / 去重合并 / 数据管线 / 冲突检测 / 预算。"""
from .extract import RawEntity, extract_text
from .enrich import enrich
from .dedup import dedup
from .pipeline import build_candidate_items, run_pipeline
from .budget_service import calc_budget, compute_budget, suggest_tradeoffs, suggest_tradeoff_items, value_ratio
from .conflict_service import detect_conflicts
from .export_service import render_itinerary, build_filename
from .expense_service import (
    add_expense, list_expenses, delete_expense, expense_summary, CATEGORIES,
)
from .destination_service import list_destinations, destination_detail
from .amap_service import (
    AmapError, geocode, regeo, search_poi, input_tips, driving,
    backfill_price_lib_coords,
)

__all__ = [
    "RawEntity",
    "extract_text",
    "enrich",
    "dedup",
    "build_candidate_items",
    "run_pipeline",
    "calc_budget",
    "compute_budget",
    "suggest_tradeoffs",
    "suggest_tradeoff_items",
    "value_ratio",
    "detect_conflicts",
    "render_itinerary",
    "build_filename",
    "add_expense",
    "list_expenses",
    "delete_expense",
    "expense_summary",
    "CATEGORIES",
    "list_destinations",
    "destination_detail",
    "AmapError",
    "geocode",
    "regeo",
    "search_poi",
    "input_tips",
    "driving",
    "backfill_price_lib_coords",
]
