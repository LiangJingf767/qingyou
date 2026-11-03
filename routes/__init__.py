# -*- coding: utf-8 -*-
"""路由蓝图统一出口。"""
from .projects import bp as projects_bp
from .engine import bp as engine_bp
from .analysis import bp as analysis_bp
from .export import bp as export_bp
from .expense import bp as expense_bp
from .destinations import bp as destinations_bp
from .map import bp as map_bp
from .pages import bp as pages_bp

__all__ = [
    "projects_bp", "engine_bp", "analysis_bp", "export_bp", "expense_bp",
    "destinations_bp", "map_bp", "pages_bp",
]
