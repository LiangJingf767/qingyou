# -*- coding: utf-8 -*-
"""大模型调用服务（BYOK）。

只依赖标准库 urllib（与 amap_service 一致，不新增 requests）。
协议：OpenAI 兼容 Chat Completions —— POST {base_url}/chat/completions。
一个实现通吃 DeepSeek / OpenAI / GLM / 本地 Ollama 等。
"""
import json
import urllib.request

_TIMEOUT = 60  # 大模型生成可能较慢，放宽到 60s


class LlmError(Exception):
    """大模型调用失败（key 错 / 超时 / 返回非法 / 解析失败）。"""


def _normalize_url(base_url: str) -> str:
    """把用户填的 base_url 规整为 chat/completions 端点。"""
    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise LlmError("缺少 base_url")
    if url.endswith("/chat/completions"):
        return url
    return url + "/chat/completions"


def call_llm(config, messages, timeout=_TIMEOUT) -> str:
    """调用 OpenAI 兼容接口，返回 assistant 文本内容。

    config: {"base_url": str, "api_key": str, "model": str}
    """
    base_url = (config or {}).get("base_url") or ""
    api_key = (config or {}).get("api_key") or ""
    model = (config or {}).get("model") or ""
    if not api_key:
        raise LlmError("缺少 API Key")
    if not model:
        raise LlmError("缺少模型名 model")

    url = _normalize_url(base_url)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "qiongyou/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise LlmError(f"接口返回 {e.code}：{detail or '请检查 base_url / key'}")
    except Exception as e:
        raise LlmError(f"请求失败：{e}")

    try:
        obj = json.loads(body)
        content = obj["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
        raise LlmError(f"响应解析失败：{e}")

    if not isinstance(content, str) or not content.strip():
        raise LlmError("大模型返回为空")
    return content.strip()
