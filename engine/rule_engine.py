# -*- coding: utf-8 -*-
"""RuleEngine：规则版行程生成引擎。

对应方案 §4.3：地理聚类分天 → 路径排序 → 约束检查 → 贪心裁剪 → 结果写回。
坐标缺失时降级为「时长均衡分天 + 类型/热门度排序」，保证离线可运行。
冲突检测（§4.6）与预算（§4.5）复用独立服务，引擎只负责「编排 + 生成」。
"""
from typing import List

from db import get_db
from models import Item
from engine.base import GenerationEngine, GenerationRequest, GenerationResult, DayPlan
from services.conflict_service import MAX_DAILY_MINUTES, MAX_DAILY_SPOTS, detect_conflicts
from services.budget_service import suggest_tradeoffs, value_ratio

# 天内排序的类型优先级（无坐标时用）：景点 → 机位 → 美食
_TYPE_ORDER = {"景点": 0, "机位": 1, "美食": 2}


class RuleEngine(GenerationEngine):
    def generate(self, request: GenerationRequest, db=None) -> GenerationResult:
        db = db or get_db()
        # 重新生成 = 全量重建：先清除历史「手动砍单」标记
        db.execute("UPDATE item SET dropped=0 WHERE project_id=?", (request.project_id,))
        items = [Item.from_row(r) for r in db.execute(
            "SELECT * FROM item WHERE project_id = ? ORDER BY popularity DESC",
            (request.project_id,),
        ).fetchall()]

        days = max(1, request.days)
        if not items:
            return GenerationResult(days=[DayPlan(day=d) for d in range(1, days + 1)])

        # 1. 分天（有坐标 → K-means 聚类；无坐标 → 时长均衡 + 尊重「第N天」提示）
        groups = self._partition(items, days)

        # 2. 天内排序
        for g in groups:
            self._sort_within_day(g)

        # 3. 贪心裁剪（强度超限 → 按性价比从低到高剔除）
        dropped, groups = self._prune(groups, request.preferences)

        # 4. 写回 day + order_no（冲突检测读 DB，须先落库）
        self._persist(groups, dropped, db)

        # 5. 冲突 + 取舍建议（复用独立服务）
        conflicts = detect_conflicts(request.project_id, db)
        suggestions = []
        if dropped:
            suggestions.append("已自动裁剪（当日强度超限）：" + "、".join(it.name for it in dropped))
        suggestions += suggest_tradeoffs(request.project_id, db=db)

        return GenerationResult(
            days=[DayPlan(day=d + 1, items=g) for d, g in enumerate(groups)],
            conflicts=conflicts,
            suggestions=suggestions,
            dropped=dropped,
        )

    # ---- 分天 ----
    def _partition(self, items: List[Item], days: int) -> List[List[Item]]:
        if all(it.lat is not None and it.lng is not None for it in items):
            return self._cluster_by_coord(items, days)
        return self._assign_by_hint(items, days)

    def _assign_by_hint(self, items: List[Item], days: int) -> List[List[Item]]:
        """无坐标降级：尊重「第N天」提示，其余按热门度塞到当前最空闲的一天。"""
        bins = [[] for _ in range(days)]
        rest = []
        for it in items:
            d = it.day
            if d is not None and 1 <= d <= days:
                bins[d - 1].append(it)
            else:
                rest.append(it)
        for it in sorted(rest, key=lambda x: -(x.popularity or 0)):
            target = min(range(days), key=lambda d: _duration(bins[d]))
            bins[target].append(it)
        return bins

    def _cluster_by_coord(self, items: List[Item], days: int) -> List[List[Item]]:
        """K-means 按坐标聚类（坐标补齐后启用）。"""
        pts = [(it.lat, it.lng) for it in items]
        step = max(1, len(pts) // days)
        centers = pts[::step][:days]
        if len(centers) < days:
            centers = centers + pts[: days - len(centers)]

        labels = [0] * len(pts)
        for _ in range(20):
            for i, p in enumerate(pts):
                labels[i] = min(range(days), key=lambda c: _dist2(p, centers[c]))
            new_centers = []
            for c in range(days):
                members = [pts[i] for i in range(len(pts)) if labels[i] == c]
                if members:
                    new_centers.append((sum(p[0] for p in members) / len(members),
                                        sum(p[1] for p in members) / len(members)))
                else:
                    new_centers.append(centers[c])
            if new_centers == centers:
                break
            centers = new_centers

        bins = [[] for _ in range(days)]
        for i, it in enumerate(items):
            bins[labels[i]].append(it)
        return bins

    # ---- 天内排序 ----
    def _sort_within_day(self, bin: List[Item]):
        if bin and all(it.lat is not None and it.lng is not None for it in bin):
            bin[:] = self._nearest_neighbor(bin)
        else:
            bin.sort(key=lambda x: (_TYPE_ORDER.get(x.type, 9), -(x.popularity or 0)))

    def _nearest_neighbor(self, bin: List[Item]) -> List[Item]:
        """就近原则：贪心最近邻（坐标补齐后启用）。"""
        rest = list(bin)
        ordered = [rest.pop(0)]
        while rest:
            last = (ordered[-1].lat, ordered[-1].lng)
            nxt = min(rest, key=lambda it: _dist2(last, (it.lat, it.lng)))
            rest.remove(nxt)
            ordered.append(nxt)
        return ordered

    # ---- 裁剪 ----
    def _prune(self, groups, preferences):
        dropped: List[Item] = []
        for g in groups:
            while _duration(g) > MAX_DAILY_MINUTES or len(g) > MAX_DAILY_SPOTS:
                worst = min(g, key=lambda it: value_ratio(it, preferences))
                g.remove(worst)
                dropped.append(worst)
        return dropped, groups

    # ---- 写回 ----
    def _persist(self, groups, dropped, db):
        for day, g in enumerate(groups, start=1):
            for order, it in enumerate(g, start=1):
                it.day, it.order_no = day, order
                db.execute("UPDATE item SET day=?, order_no=? WHERE id=?", (day, order, it.id))
        for it in dropped:
            db.execute("UPDATE item SET day=NULL, order_no=NULL WHERE id=?", (it.id,))
        db.commit()


# ---- 工具 ----
def _duration(bin: List[Item]) -> int:
    return sum(it.est_duration or 0 for it in bin)


def _dist2(a, b) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
