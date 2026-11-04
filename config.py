# -*- coding: utf-8 -*-
"""全局配置。"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    """应用配置。"""

    # SQLite 数据库路径
    DATABASE = os.path.join(BASE_DIR, "qiongyou.db")

    # 高德开放平台 Key
    AMAP_KEY = os.getenv("AMAP_KEY", "")
    AMAP_JS_KEY = os.getenv("AMAP_JS_KEY", "")
    AMAP_JS_SECURITY_CODE = os.getenv("AMAP_JS_SECURITY_CODE", "")

    # 腾讯云 OCR
    OCR_SECRET_ID = os.getenv("OCR_SECRET_ID", "")
    OCR_SECRET_KEY = os.getenv("OCR_SECRET_KEY", "")
    OCR_REGION = "ap-guangzhou"

    # 心知天气
    SENIVERSE_PUBLIC_KEY = os.getenv("SENIVERSE_PUBLIC_KEY", "")
    SENIVERSE_PRIVATE_KEY = os.getenv("SENIVERSE_PRIVATE_KEY", "")

    # 图片上传目录与大小限制
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
