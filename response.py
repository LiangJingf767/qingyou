# -*- coding: utf-8 -*-
"""统一响应格式工具。

响应结构：{"code": <int>, "message": <str>, "data": <dict|list>}

错误码约定（方案 §4.1）：
    0     成功
    1xxx  参数 / 请求错误
    2xxx  业务错误（含资源不存在）
    3xxx  外部依赖错误（高德 / OCR / 大模型）

约定：所有响应 HTTP 状态码统一为 200，业务结果由 body 里的 code 表达，
前端只需判断 code == 0 即可。
"""
from flask import jsonify

# 错误码常量
CODE_OK = 0
CODE_PARAM_ERROR = 1000      # 参数错误 / 缺少参数
CODE_BIZ_ERROR = 2000        # 业务处理失败
CODE_NOT_FOUND = 2004        # 资源不存在
CODE_EXT_ERROR = 3000        # 外部依赖错误


def ok(data=None, message="ok"):
    """成功响应。"""
    return jsonify({
        "code": CODE_OK,
        "message": message,
        "data": data if data is not None else {},
    })


def fail(code, message="error", data=None):
    """失败响应。"""
    return jsonify({
        "code": code,
        "message": message,
        "data": data if data is not None else {},
    })


def bad_request(message="参数错误"):
    """1xxx 参数错误。"""
    return fail(CODE_PARAM_ERROR, message)


def not_found(message="资源不存在"):
    """2xxx 资源不存在。"""
    return fail(CODE_NOT_FOUND, message)
