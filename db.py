# -*- coding: utf-8 -*-
"""SQLite 连接管理（Flask g 模式，无 ORM）。"""
import sqlite3

from flask import g

from config import Config


def get_db():
    """获取当前请求的数据库连接（复用），并开启外键约束。"""
    if "db" not in g:
        g.db = sqlite3.connect(Config.DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """请求结束时关闭连接。"""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """注册 teardown 钩子。"""
    app.teardown_appcontext(close_db)
