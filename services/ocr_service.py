# -*- coding: utf-8 -*-
"""腾讯云文字识别（OCR）服务：截图 → 文本。

接口：腾讯云 OCR「通用印刷体识别」GeneralBasicOCR（API 3.0，TC3-HMAC-SHA256 签名）。
只依赖标准库，与 amap_service / llm_service 一致，不新增第三方依赖。
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.request
from datetime import datetime

from config import Config

_HOST = "ocr.tencentcloudapi.com"
_SERVICE = "ocr"
_ACTION = "GeneralBasicOCR"
_VERSION = "2018-11-19"
_TIMEOUT = 15


class OcrError(Exception):
    """OCR 调用失败（网络 / 鉴权 / 返回错误 / 无文本）。"""


def _sign_tc3(secret_id, secret_key, host, action, version, region, payload):
    """腾讯云 API 3.0 TC3-HMAC-SHA256 签名。"""
    algorithm = "TC3-HMAC-SHA256"
    timestamp = int(time.time())
    date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")

    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    )

    credential_scope = f"{date}/{_SERVICE}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

    def _hmac(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _hmac(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _hmac(secret_date, _SERVICE)
    secret_signing = _hmac(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": ct,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
        "X-TC-Region": region,
    }


def ocr_image(image_bytes: bytes) -> str:
    """识别图片中的文字，返回按行拼接的文本；无结果/失败抛 OcrError。"""
    secret_id = (Config.OCR_SECRET_ID or "").strip()
    secret_key = (Config.OCR_SECRET_KEY or "").strip()
    if not secret_id:
        raise OcrError("未配置 OCR SecretId（请在 config.py 补全）")
    if not secret_key:
        raise OcrError("未配置 OCR SecretKey")

    payload = json.dumps({"ImageBase64": base64.b64encode(image_bytes).decode("ascii")})
    headers = _sign_tc3(secret_id, secret_key, _HOST, _ACTION, _VERSION,
                        Config.OCR_REGION, payload)
    req = urllib.request.Request(
        f"https://{_HOST}/",
        data=payload.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise OcrError(f"OCR 接口返回 {e.code}：{detail}")
    except Exception as e:
        raise OcrError(f"OCR 请求失败：{e}")

    try:
        obj = json.loads(body)
    except json.JSONDecodeError as e:
        raise OcrError(f"OCR 返回非 JSON：{e}")

    resp = obj.get("Response") or {}
    if "Error" in resp:
        err = resp["Error"]
        raise OcrError(f"OCR 错误：{err.get('Message') or err.get('Code')}")

    lines = [d.get("DetectedText", "").strip() for d in resp.get("TextDetections") or []]
    text = "\n".join(x for x in lines if x)
    if not text:
        raise OcrError("图片中未识别到文字")
    return text
