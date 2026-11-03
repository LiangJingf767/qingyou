# -*- coding: utf-8 -*-
"""心知天气（Seniverse）逐日预报封装。

使用 v3 免费接口 daily.json：key 传私钥，location 传城市名（支持中文），
返回从今天起 N 天的预报（text_day/high/low 等），供行程页按天展示。
"""
import json
import urllib.parse
import urllib.request

from config import Config

_API = "https://api.seniverse.com/v3/weather/daily.json"


class WeatherError(Exception):
    """心知天气调用失败。"""


def daily_forecast(city, days=3):
    """返回 [{date, text_day, text_night, high, low, wind_direction, wind_scale}...]。"""
    if not city:
        raise WeatherError("缺少城市")

    params = {
        "key": Config.SENIVERSE_PRIVATE_KEY,
        "location": city,
        "language": "zh-Hans",
        "unit": "c",
        "start": 0,
        "days": max(1, min(int(days or 3), 15)),
    }
    url = _API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "qiongyou/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 —— 网络/JSON 异常统一抛业务错误
        raise WeatherError(f"天气服务不可用：{e}")

    results = data.get("results") or []
    if not results:
        raise WeatherError(data.get("status") or "天气服务未返回数据")

    daily = results[0].get("daily") or []
    return [
        {
            "date": d.get("date"),
            "text_day": d.get("text_day"),
            "text_night": d.get("text_night"),
            "high": d.get("high"),
            "low": d.get("low"),
            "wind_direction": d.get("wind_direction"),
            "wind_scale": d.get("wind_scale"),
        }
        for d in daily
    ]
