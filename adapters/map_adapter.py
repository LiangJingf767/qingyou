# -*- coding: utf-8 -*-
"""地图适配器：封装高德地理编码 / 路径规划，无 Key 或失败时降级。

业务层（enrich 等）只依赖此适配器的“不抛异常”契约：
成功返回 dict；无 Key / 网络失败 / 无结果一律返回 None，绝不阻断主流程。
完整的高德能力（POI 搜索 / 输入提示 / 逆地理 / 驾车规划）见 services/amap_service。
"""
from typing import List, Optional

from config import Config
from services.amap_service import AmapError, geocode, driving


class MapAdapter:
    """高德 Web 服务封装。业务只调此接口，不直接 import 高德 SDK。"""

    def geocode(self, name: str, city: str) -> Optional[dict]:
        """地理编码 → {'lat':.., 'lng':..}；无 Key / 失败 → None（降级）。"""
        if not Config.AMAP_KEY or Config.AMAP_KEY == "YOUR_AMAP_KEY":
            return None
        try:
            res = geocode(name, city=city)
        except AmapError:
            return None
        if not res or res[0].get("lng") is None:
            return None
        g = res[0]
        return {"lat": g["lat"], "lng": g["lng"]}

    def route(self, stops: List[dict], city: str) -> Optional[dict]:
        """相邻站点驾车距离/时长累加；缺坐标或失败返回 None。city 预留未用。"""
        if not stops or len(stops) < 2:
            return None
        total_distance = total_duration = 0
        for a, b in zip(stops, stops[1:]):
            if not (a.get("lat") and a.get("lng") and b.get("lat") and b.get("lng")):
                return None
            try:
                r = driving((a["lng"], a["lat"]), (b["lng"], b["lat"]))
            except AmapError:
                return None
            if not r:
                return None
            total_distance += r["distance"]
            total_duration += r["duration"]
        return {"distance": total_distance, "duration": total_duration}
