# -*- coding: utf-8 -*-
"""应用入口：创建应用、初始化数据库、注册蓝图、统一错误处理。"""
import socket

from flask import Flask

from config import Config
from db import init_app as init_db_app
from response import ok, fail, CODE_NOT_FOUND, CODE_EXT_ERROR
from routes import (
    projects_bp, engine_bp, analysis_bp, export_bp, expense_bp,
    destinations_bp, map_bp, pages_bp,
)
from routes.pages import icon_svg


def create_app():
    """应用工厂。"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # 模板全局：inline 图标（与前端 api.js 的 icon() 同源）
    app.jinja_env.globals["icon"] = icon_svg

    # 中文 JSON 不转义（兼容 Flask 2.x / 3.x）
    app.config["JSON_AS_ASCII"] = False
    try:
        app.json.ensure_ascii = False
    except Exception:
        pass

    # 数据库连接管理
    init_db_app(app)

    # 注册业务蓝图
    app.register_blueprint(projects_bp)
    app.register_blueprint(engine_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(expense_bp)
    app.register_blueprint(destinations_bp)
    app.register_blueprint(map_bp)

    # 前端页面（必须最后注册，其 /<path:name> 兜底路由不影响 /api/v1）
    app.register_blueprint(pages_bp)

    # 健康检查
    @app.route("/api/v1/ping", methods=["GET"])
    def ping():
        return ok()

    # 统一错误处理：未命中路由 / 服务器异常也返回统一信封
    @app.errorhandler(404)
    def handle_404(e):
        return fail(CODE_NOT_FOUND, "接口不存在")

    @app.errorhandler(500)
    def handle_500(e):
        return fail(CODE_EXT_ERROR, "服务器内部错误")

    return app


app = create_app()


def _lan_ip():
    """探测本机局域网 IP（用 UDP 连一个公网地址获取出接口地址，不真正发包）。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    ip = _lan_ip()
    print("=" * 48)
    print("  穷游行程助手已启动")
    print(f"  本机访问  : http://127.0.0.1:5000")
    print(f"  局域网访问: http://{ip}:5000")
    print("  同一 WiFi 下的手机/同学浏览器打开上面的局域网地址")
    print("=" * 48)
    app.run(host="0.0.0.0", port=5000, debug=True)
