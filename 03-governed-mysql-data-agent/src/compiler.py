from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from .catalog import (
    METRIC_CATALOG,
    CompilerStrategy,
    MetricDefinition,
)
from .semantic import PLAN_READY, SemanticPlan
from .verification import ResultContract


ALLOWED_REGION_VALUES = frozenset({"east", "west", "north", "south"})


class CompileError(ValueError):
    """Raised when a structured plan cannot be compiled without losing meaning."""


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    result_metric: str
    result_contract: ResultContract
    params: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if self.result_contract.expected_key != self.result_metric:
            raise ValueError(
                "result contract key must match compiled result metric"
            )


def _validated_region(
    filters: dict[str, str], allowed_fields: frozenset[str]
) -> str | None:
    unknown_fields = set(filters) - allowed_fields
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


def _compiled_query(
    definition: MetricDefinition,
    sql: str,
    *,
    region: str | None = None,
    params: tuple[Any, ...] = (),
) -> CompiledQuery:
    result_metric = definition.metric_id
    contract = definition.result_contract
    if region is not None:
        result_metric = f"{region}_{definition.metric_id}"
        contract = replace(contract, expected_key=result_metric)
    return CompiledQuery(
        sql=sql,
        result_metric=result_metric,
        result_contract=contract,
        params=params,
    )


def _compile_revenue(
    definition: MetricDefinition, region: str | None
) -> CompiledQuery:
    if region is not None:
        return _compiled_query(
            definition,
            sql=(
                "SELECT ROUND(COALESCE((SELECT SUM(p.amount) FROM payments AS p "
                "JOIN orders AS o ON o.id=p.order_id WHERE p.status='completed' "
                "AND o.region=?),0) - COALESCE((SELECT SUM(r.amount) FROM refunds AS r "
                "JOIN orders AS o ON o.id=r.order_id WHERE r.status='completed' "
                "AND o.region=?),0),2) AS revenue"
            ),
            region=region,
            params=(region, region),
        )
    return _compiled_query(
        definition,
        sql=(
            "SELECT ROUND(COALESCE((SELECT SUM(amount) FROM payments "
            "WHERE status='completed'),0) - COALESCE((SELECT SUM(amount) "
            "FROM refunds WHERE status='completed'),0),2) AS revenue"
        ),
    )


def _compile_completed_order_count(
    definition: MetricDefinition, region: str | None
) -> CompiledQuery:
    if region is not None:
        return _compiled_query(
            definition,
            sql=(
                "SELECT COUNT(*) AS completed_orders FROM orders "
                "WHERE status='completed' AND region=?"
            ),
            region=region,
            params=(region,),
        )
    return _compiled_query(
        definition,
        sql=(
            "SELECT COUNT(*) AS completed_orders FROM orders "
            "WHERE status='completed'"
        ),
    )


def _compile_avg_completed_order_value(
    definition: MetricDefinition, region: str | None
) -> CompiledQuery:
    if region is not None:
        return _compiled_query(
            definition,
            sql=(
                "SELECT ROUND(AVG(total),2) AS avg_order_value FROM orders "
                "WHERE status='completed' AND region=?"
            ),
            region=region,
            params=(region,),
        )
    return _compiled_query(
        definition,
        sql=(
            "SELECT ROUND(AVG(total),2) AS avg_order_value FROM orders "
            "WHERE status='completed'"
        ),
    )


def _compile_completed_payment_sum(
    definition: MetricDefinition, region: str | None
) -> CompiledQuery:
    if region is not None:
        raise CompileError("completed payments do not support region filters")
    return _compiled_query(
        definition,
        sql=(
            "SELECT ROUND(COALESCE(SUM(amount),0),2) AS completed_payments "
            "FROM payments WHERE status='completed'"
        ),
    )


def _compile_completed_refund_sum(
    definition: MetricDefinition, region: str | None
) -> CompiledQuery:
    if region is not None:
        raise CompileError("completed refunds do not support region filters")
    return _compiled_query(
        definition,
        sql=(
            "SELECT ROUND(COALESCE(SUM(amount),0),2) AS completed_refunds "
            "FROM refunds WHERE status='completed'"
        ),
    )


CompilerFunction = Callable[[MetricDefinition, str | None], CompiledQuery]
_STRATEGY_COMPILERS: dict[CompilerStrategy, CompilerFunction] = {
    CompilerStrategy.REVENUE: _compile_revenue,
    CompilerStrategy.COMPLETED_ORDER_COUNT: _compile_completed_order_count,
    CompilerStrategy.AVG_COMPLETED_ORDER_VALUE: (
        _compile_avg_completed_order_value
    ),
    CompilerStrategy.COMPLETED_PAYMENT_SUM: _compile_completed_payment_sum,
    CompilerStrategy.COMPLETED_REFUND_SUM: _compile_completed_refund_sum,
}
STRATEGY_COMPILERS: Mapping[CompilerStrategy, CompilerFunction] = (
    MappingProxyType(_STRATEGY_COMPILERS)
)


def compile_plan(plan: SemanticPlan) -> CompiledQuery:
    """Compile only an explicit SemanticPlan; never inspect the user question."""
    if not isinstance(plan, SemanticPlan):
        raise CompileError("invalid semantic plan shape / 无效的语义计划形状")
    if plan.status != PLAN_READY or plan.metric is None:
        raise CompileError("semantic plan is not ready / 语义计划尚不可执行")
    definition = METRIC_CATALOG.get(plan.metric)
    if definition is None:
        raise CompileError(f"unsupported metric: {plan.metric} / 不支持的业务指标")
    if not isinstance(plan.filters, dict):
        raise CompileError("invalid filters shape / 无效的过滤条件形状")

    region = _validated_region(plan.filters, definition.allowed_filters)
    compiler = STRATEGY_COMPILERS.get(definition.compiler_strategy)
    if compiler is None:
        raise CompileError(
            f"unsupported compiler strategy: {definition.compiler_strategy}"
        )
    return compiler(definition, region)
