# -*- coding: utf-8 -*-
"""全局配置模板（不含真实密钥）。

用法：
    1. 复制本文件为 config.py：  cp config.example.py config.py
    2. 在 config.py 里填入你的真实 Key（高德 / 腾讯 OCR / 心知天气）。
    3. config.py 已被 .gitignore 忽略，不会上传到 GitHub；部署到服务器时再把真的 config.py 传上去。

留空或保持 "YOUR_..." 占位符时，对应能力会自动降级（地图/坐标/OCR/天气不可用），不影响主流程。
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    """应用配置。"""

    # SQLite 数据库路径
    DATABASE = os.path.join(BASE_DIR, "qiongyou.db")

    # 高德开放平台 Key
    #   AMAP_KEY：Web服务 Key（后端调用，绝不能下发到前端）
    #   AMAP_JS_KEY：Web端 JS API Key（前端地图用，域名白名单在高德控制台配置）
    #   AMAP_JS_SECURITY_CODE：JS API v2.0 安全密钥；留空则前端自动退回 v1.4.15（仅需 Key）
    AMAP_KEY = "YOUR_AMAP_KEY"
    AMAP_JS_KEY = "YOUR_AMAP_JS_KEY"
    AMAP_JS_SECURITY_CODE = ""

    # 腾讯云 OCR（截图识别 → 文本，接入「追加攻略」/ 录入页截图 OCR）
    #   SecretId 形如 AKIDxxxxxxxx，需与 SecretKey 配套使用
    OCR_SECRET_ID = "YOUR_OCR_SECRET_ID"
    OCR_SECRET_KEY = "YOUR_OCR_SECRET_KEY"
    OCR_REGION = "ap-guangzhou"

    # 心知天气（Seniverse）API —— 公钥/私钥
    SENIVERSE_PUBLIC_KEY = "YOUR_SENIVERSE_PUBLIC_KEY"
    SENIVERSE_PRIVATE_KEY = "YOUR_SENIVERSE_PRIVATE_KEY"

    # 图片上传目录与大小限制
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    DEBUG = True
