# -*- coding: utf-8 -*-
"""大模型结构化地点提取：把整段攻略文案交给用户配置的大模型（BYOK），
按严格 JSON 提取地点名称/类型/天数/备注，替代纯正则提取。失败时由调用方降级正则。
"""
import json
import re
from typing import List

from services.extract import RawEntity
from services.llm_service import call_llm

_SYSTEM = (
    "你是专业的旅游攻略地点提取器。你的任务是从用户的旅游攻略文案中提取「地点名称」。\n"
    "严格规则：\n"
    "1. 只提取真实的景点、餐厅、酒店或具体地标名称，不要编造。\n"
    "2. 必须过滤掉所有废话、修饰词、形容词（如「楼下就有」「超多」「每一个」「好」「这」）。\n"
    "3. 必须把时间词（中午、上午、下午、晚上、早上）和动词（去、吃、逛、玩、看、住、喝）与地点名称剥离开。"
    "例如「中午去太琼糟粕醋吃饭」，只能提取「太琼糟粕醋」，type 为「美食」。\n"
    "4. 如果一句话里没有具体地名（如「这，每一个」「酒店楼下就有好」），直接丢弃，不要输出。\n"
    "5. 根据上下文把地点归类到 Day1、Day2、Day3（原文没有明确天数时按出现顺序归入）。\n"
    "6. type 只能是：景点 / 美食 / 住宿 / 机位 之一。\n"
    "必须输出纯 JSON，不要任何 Markdown 符号、代码块或解释。"
)

_JSON_TEMPLATE = json.dumps({
    "itinerary": [
        {
            "day": "Day1",
            "items": [
                {"name": "嗲嗲的椰子鸡", "type": "美食", "notes": "酒店楼下，推荐鸳鸯锅"}
            ]
        }
    ]
}, ensure_ascii=False)

# 类型归一化到系统内 景点/美食/住宿/机位
_TYPE_MAP = {
    "景点": "景点", "景区": "景点", "公园": "景点", "博物馆": "景点", "地标": "景点",
    "美食": "美食", "餐饮": "美食", "餐厅": "美食", "小吃": "美食", "饭店": "美食", "吃": "美食",
    "住宿": "住宿", "酒店": "住宿", "民宿": "住宿", "客栈": "住宿",
    "机位": "机位", "拍照": "机位", "打卡": "机位",
}


def _normalize_type(t):
    if not t:
        return "景点"
    t = str(t).strip()
    for k, v in _TYPE_MAP.items():
        if k in t:
            return v
    return "景点"


def _parse_day(d):
    m = re.search(r"\d+", str(d or ""))
    return int(m.group()) if m else None


def _parse_json(content: str) -> dict:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    else:
        text = re.sub(r"^```|```$", "", text).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e > s:
            obj = json.loads(text[s:e + 1])
        else:
            raise
    if not isinstance(obj, dict):
        raise ValueError("大模型返回不是对象")
    return obj


def extract_locations(text: str, llm_config: dict) -> List[RawEntity]:
    """调用大模型提取地点，返回 RawEntity 列表（带 note/type/day）。失败抛异常。"""
    content = call_llm(llm_config, [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": text + "\n\n请按上述格式提取地点：" + _JSON_TEMPLATE},
    ])
    obj = _parse_json(content)
    out = []
    for day_obj in obj.get("itinerary") or []:
        day = _parse_day(day_obj.get("day"))
        for it in day_obj.get("items") or []:
            name = (it.get("name") or "").strip()
            if not name:
                continue
            notes = (it.get("notes") or "").strip() or None
            out.append(RawEntity(
                name=name,
                type=_normalize_type(it.get("type")),
                day=day,
                note=notes,
            ))
    return out
