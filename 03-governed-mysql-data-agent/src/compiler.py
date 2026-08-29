from dataclasses import dataclass
from typing import Any

from .semantic import METRICS, PLAN_READY, SemanticPlan


ALLOWED_FILTER_FIELDS = frozenset({"region"})
ALLOWED_FILTER_OPERATORS = {"region": "="}
ALLOWED_REGION_VALUES = frozenset({"east", "west", "north", "south"})


class CompileError(ValueError):
    """Raised when a structured plan cannot be compiled without losing meaning."""


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    result_metric: str
    params: tuple[Any, ...] = ()


BASE_SQL = {
    "revenue": (
        "SELECT ROUND(COALESCE((SELECT SUM(amount) FROM payments "
        "WHERE status='completed'),0) - COALESCE((SELECT SUM(amount) "
        "FROM refunds WHERE status='completed'),0),2) AS revenue"
    ),
    "completed_orders": (
        "SELECT COUNT(*) AS completed_orders FROM orders "
        "WHERE status='completed'"
    ),
    "avg_order_value": (
        "SELECT ROUND(AVG(total),2) AS avg_order_value FROM orders "
        "WHERE status='completed'"
    ),
}


def _validated_region(filters: dict[str, str]) -> str | None:
    unknown_fields = set(filters) - ALLOWED_FILTER_FIELDS
    if unknown_fields:
        fields = ", ".join(sorted(str(field) for field in unknown_fields))
        raise CompileError(f"unsupported filter field: {fields} / 不支持的过滤字段")

    if "region" not in filters:
        return None

    value = filters["region"]
    if not isinstance(value, str) or not value.strip():
        raise CompileError("unsupported region value shape / 不支持的地域值形状")

    region = value.strip().lower()
    if region not in ALLOWED_REGION_VALUES:
        raise CompileError(f"unsupported region value: {region} / 不支持的地域值")
    return region


def _compile_region_query(metric: str, region: str) -> CompiledQuery:
    result_metric = f"{region}_{metric}"
    if metric == "revenue":
        return CompiledQuery(
            sql=(
                "SELECT ROUND(COALESCE((SELECT SUM(p.amount) FROM payments AS p "
                "JOIN orders AS o ON o.id=p.order_id WHERE p.status='completed' "
                "AND o.region=?),0) - COALESCE((SELECT SUM(r.amount) FROM refunds AS r "
                "JOIN orders AS o ON o.id=r.order_id WHERE r.status='completed' "
                "AND o.region=?),0),2) AS revenue"
            ),
            result_metric=result_metric,
            params=(region, region),
        )
    if metric == "completed_orders":
        return CompiledQuery(
            sql=(
                "SELECT COUNT(*) AS completed_orders FROM orders "
                "WHERE status='completed' AND region=?"
            ),
            result_metric=result_metric,
            params=(region,),
        )
    if metric == "avg_order_value":
        return CompiledQuery(
            sql=(
                "SELECT ROUND(AVG(total),2) AS avg_order_value FROM orders "
                "WHERE status='completed' AND region=?"
            ),
            result_metric=result_metric,
            params=(region,),
        )
    raise CompileError(f"unsupported metric: {metric} / 不支持的业务指标")


def compile_plan(plan: SemanticPlan) -> CompiledQuery:
    """Compile only an explicit SemanticPlan; never inspect the user question."""
    if not isinstance(plan, SemanticPlan):
        raise CompileError("invalid semantic plan shape / 无效的语义计划形状")
    if plan.status != PLAN_READY or plan.metric is None:
        raise CompileError("semantic plan is not ready / 语义计划尚不可执行")
    if plan.metric not in METRICS or plan.metric not in BASE_SQL:
        raise CompileError(f"unsupported metric: {plan.metric} / 不支持的业务指标")
    if not isinstance(plan.filters, dict):
        raise CompileError("invalid filters shape / 无效的过滤条件形状")

    region = _validated_region(plan.filters)
    if region is None:
        return CompiledQuery(
            sql=BASE_SQL[plan.metric], result_metric=plan.metric
        )
    return _compile_region_query(plan.metric, region)
