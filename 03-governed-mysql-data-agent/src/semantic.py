import re
from dataclasses import asdict, dataclass


METRICS = {
    "revenue": {
        "description": "Completed payment amount minus completed refunds / 已完成付款减已完成退款",
        "sql": "SELECT ROUND(COALESCE((SELECT SUM(amount) FROM payments WHERE status='completed'),0) - COALESCE((SELECT SUM(amount) FROM refunds WHERE status='completed'),0),2) AS revenue",
    },
    "completed_orders": {
        "description": "Count of completed orders / 已完成订单数量",
        "sql": "SELECT COUNT(*) AS completed_orders FROM orders WHERE status='completed'",
    },
    "avg_order_value": {
        "description": "Average total for completed orders / 已完成订单平均客单价",
        "sql": "SELECT ROUND(AVG(total),2) AS avg_order_value FROM orders WHERE status='completed'",
    },
}


PLAN_READY = "READY"
PLAN_NEEDS_CLARIFICATION = "NEED_CLARIFICATION"
ALIASES = {
    "收入": "revenue",
    "营收": "revenue",
    "订单数": "completed_orders",
    "客单价": "avg_order_value",
}
UNSPECIFIED_SCOPE_MARKERS = ("一下",)
REGION_PATTERNS = (
    re.compile(r"\b(east|west|north|south)\s+region\b", re.I),
    re.compile(r"\bregion\s+(east|west|north|south)\b", re.I),
)


@dataclass(frozen=True)
class SemanticPlan:
    metric: str | None
    filters: dict[str, str]
    status: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _metric_candidates(question: str) -> list[str]:
    lowered = question.lower()
    candidates = []
    for alias, metric in ALIASES.items():
        if alias in question and metric not in candidates:
            candidates.append(metric)
    for metric in METRICS:
        if metric in lowered and metric not in candidates:
            candidates.append(metric)
    return candidates


def _filters(question: str) -> dict[str, str]:
    for pattern in REGION_PATTERNS:
        match = pattern.search(question)
        if match:
            return {"region": match.group(1).lower()}
    return {}


def _scope_is_ambiguous(question: str) -> bool:
    return any(marker in question for marker in UNSPECIFIED_SCOPE_MARKERS)


def build_semantic_plan(question: str) -> SemanticPlan:
    """Resolve only semantics that the current deterministic runtime can execute."""
    candidates = _metric_candidates(question)
    filters = _filters(question)

    if not candidates:
        return SemanticPlan(
            metric=None,
            filters=filters,
            status=PLAN_NEEDS_CLARIFICATION,
            reason="unknown business metric / 未知业务指标",
        )

    if len(candidates) > 1:
        return SemanticPlan(
            metric=None,
            filters=filters,
            status=PLAN_NEEDS_CLARIFICATION,
            reason="multiple business metrics require clarification / 多个业务指标需要澄清",
        )

    metric = candidates[0]
    if _scope_is_ambiguous(question):
        return SemanticPlan(
            metric=metric,
            filters=filters,
            status=PLAN_NEEDS_CLARIFICATION,
            reason="query scope requires clarification / 查询范围需要澄清",
        )

    if filters:
        return SemanticPlan(
            metric=metric,
            filters=filters,
            status=PLAN_NEEDS_CLARIFICATION,
            reason="recognized filters are not yet executable / 已识别过滤条件暂不可执行",
        )

    return SemanticPlan(
        metric=metric,
        filters={},
        status=PLAN_READY,
        reason="ready / 可执行",
    )


def resolve_metric(question: str):
    """Backward-compatible metric view of an executable semantic plan."""
    plan = build_semantic_plan(question)
    return plan.metric if plan.status == PLAN_READY else None
