"""Finite SQL compiler for validated Domain Profile operations."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from .catalog import CompilerStrategy
from .profile import (
    AggregateOperation,
    DifferenceOfSumsOperation,
    DomainProfile,
    MetricDefinition,
    load_default_profile,
)
from .semantic import (
    ORDER_METRIC_ASC,
    ORDER_METRIC_DESC,
    PLAN_READY,
    DateRange,
    SemanticPlan,
)
from .verification import ResultContract


class CompileError(ValueError):
    """Raised when a structured plan cannot be compiled without losing meaning."""


MAX_GROUPED_ROWS = 100
GROUPED_OVERFLOW_LIMIT = MAX_GROUPED_ROWS + 1


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    result_metric: str
    result_contract: ResultContract
    params: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        if self.result_contract.expected_key != self.result_metric:
            raise ValueError("result contract key must match compiled result metric")


def _validated_filters(
    plan: SemanticPlan,
    definition: MetricDefinition,
    profile: DomainProfile,
) -> dict[str, str]:
    unknown_fields = set(plan.filters) - definition.allowed_filters
    if unknown_fields:
        fields = ", ".join(sorted(str(field) for field in unknown_fields))
        raise CompileError(f"unsupported filter field: {fields} / 不支持的过滤字段")
    result = {}
    for field, value in plan.filters.items():
        if not isinstance(value, str) or not value.strip():
            raise CompileError(
                f"unsupported {field} value shape / 不支持的过滤值形状"
            )
        normalized = value.strip().lower()
        dimension = profile.dimensions[field]
        if normalized not in dimension.allowed_values:
            raise CompileError(
                f"unsupported {field} value: {normalized} / 不支持的过滤值"
            )
        result[field] = normalized
    return result


def _result_parts(
    definition: MetricDefinition, filters: dict[str, str]
) -> tuple[str, ResultContract]:
    result_metric = definition.metric_id
    contract = definition.result_contract
    if definition.result_key.mode == "dimension_value_prefix" and filters:
        value = filters[next(iter(filters))]
        result_metric = f"{value}_{definition.metric_id}"
        contract = replace(contract, expected_key=result_metric)
    return result_metric, contract


def _where(predicates: list[str]) -> str:
    return " WHERE " + " AND ".join(predicates) if predicates else ""


def _aggregate_expression(operation: AggregateOperation) -> str:
    if operation.aggregate == "count":
        expression = "COUNT(*)"
    else:
        expression = f"{operation.aggregate.upper()}({operation.column})"
    if operation.coalesce_zero:
        expression = f"COALESCE({expression},0)"
    if operation.round_digits is not None:
        expression = f"ROUND({expression},{operation.round_digits})"
    return expression


def _compile_aggregate(
    definition: MetricDefinition,
    operation: AggregateOperation,
    filters: dict[str, str],
    plan: SemanticPlan,
    profile: DomainProfile,
) -> CompiledQuery:
    result_metric, contract = _result_parts(definition, filters)
    predicates = [
        f"{predicate.column}='{predicate.value}'"
        for predicate in operation.fixed_predicates
    ]
    params = []
    for field, value in filters.items():
        predicates.append(f"{operation.filter_bindings[field].column}=?")
        params.append(value)
    if plan.time_range is not None:
        binding = operation.filter_bindings[plan.time_range.dimension]
        predicates.extend((f"{binding.column}>=?", f"{binding.column}<?"))
        params.extend(
            (
                plan.time_range.start_inclusive.isoformat(),
                plan.time_range.end_exclusive.isoformat(),
            )
        )
    expression = _aggregate_expression(operation)
    if plan.group_by is not None:
        dimension = profile.dimensions[plan.group_by]
        dimension_column = dimension.column
        if dimension_column is None:
            raise CompileError("group-by dimension has no approved column")
        if plan.order == ORDER_METRIC_DESC:
            order_clause = f" ORDER BY {definition.metric_id} DESC, {plan.group_by} ASC"
        elif plan.order == ORDER_METRIC_ASC:
            order_clause = f" ORDER BY {definition.metric_id} ASC, {plan.group_by} ASC"
        else:
            order_clause = f" ORDER BY {plan.group_by} ASC"
        sql_limit = plan.limit if plan.limit is not None else GROUPED_OVERFLOW_LIMIT
        sql = (
            f"SELECT {dimension_column} AS {plan.group_by}, "
            f"{expression} AS {definition.metric_id} "
            f"FROM {operation.source.table}{_where(predicates)} "
            f"GROUP BY {dimension_column}{order_clause} LIMIT ?"
        )
        params.append(sql_limit)
        contract = ResultContract.grouped_numeric(
            expected_key=result_metric,
            dimension_key=plan.group_by,
            max_rows=MAX_GROUPED_ROWS,
            requested_limit=plan.limit,
            order=plan.order or "dimension_asc",
        )
        return CompiledQuery(
            sql=sql,
            result_metric=result_metric,
            result_contract=contract,
            params=tuple(params),
        )
    sql = (
        f"SELECT {expression} AS {definition.metric_id} "
        f"FROM {operation.source.table}{_where(predicates)}"
    )
    return CompiledQuery(
        sql=sql,
        result_metric=result_metric,
        result_contract=contract,
        params=tuple(params),
    )


def _sum_subquery(side, join, *, right: bool, filtered: bool) -> str:
    if not filtered:
        predicates = [
            f"{item.column}='{item.value}'" for item in side.fixed_predicates
        ]
        return (
            f"SELECT SUM({side.column}) FROM {side.source.table}"
            f"{_where(predicates)}"
        )
    join_side = join.right_join if right else join.left_join
    source_alias = side.source.alias
    predicates = [
        f"{source_alias}.{item.column}='{item.value}'"
        for item in side.fixed_predicates
    ]
    predicates.append(f"{join.alias}.{join.value_column}=?")
    return (
        f"SELECT SUM({source_alias}.{side.column}) FROM {side.source.table} "
        f"AS {source_alias} JOIN {join.table} AS {join.alias} ON "
        f"{join.alias}.{join_side.target_column}="
        f"{source_alias}.{join_side.source_column}{_where(predicates)}"
    )


def _compile_difference(
    definition: MetricDefinition,
    operation: DifferenceOfSumsOperation,
    filters: dict[str, str],
) -> CompiledQuery:
    result_metric, contract = _result_parts(definition, filters)
    join = None
    params: tuple[Any, ...] = ()
    if filters:
        field, value = next(iter(filters.items()))
        join = operation.filter_joins[field]
        params = (value, value)
    left = _sum_subquery(
        operation.left, join, right=False, filtered=join is not None
    )
    right = _sum_subquery(
        operation.right, join, right=True, filtered=join is not None
    )
    sql = (
        f"SELECT ROUND(COALESCE(({left}),0) - COALESCE(({right}),0),"
        f"{operation.round_digits}) AS {definition.metric_id}"
    )
    return CompiledQuery(sql, result_metric, contract, params)


def _validate_analytics(
    plan: SemanticPlan,
    definition: MetricDefinition,
    profile: DomainProfile,
) -> None:
    if plan.time_range is not None:
        if not isinstance(plan.time_range, DateRange):
            raise CompileError("invalid time range shape / 无效的时间范围形状")
        dimension_id = plan.time_range.dimension
        dimension = profile.dimensions.get(dimension_id)
        if (
            dimension is None
            or dimension.dimension_type != "date"
            or not dimension.filterable
            or dimension_id not in definition.allowed_filters
        ):
            raise CompileError("unsupported time dimension / 不支持的时间维度")
        binding = getattr(definition.operation, "filter_bindings", {}).get(
            dimension_id
        )
        if binding is None or binding.column != dimension.column:
            raise CompileError("time dimension binding mismatch / 时间维度绑定不匹配")
        if plan.time_range.start_inclusive >= plan.time_range.end_exclusive:
            raise CompileError("time range must be non-empty / 时间范围必须非空")
    if plan.group_by is None:
        if plan.order is not None or plan.limit is not None:
            raise CompileError("ranking requires group-by / 排名需要分组")
        return
    if (
        not isinstance(plan.group_by, str)
        or plan.group_by not in definition.allowed_group_by
    ):
        raise CompileError("unsupported group-by dimension / 不支持的分组维度")
    dimension = profile.dimensions.get(plan.group_by)
    if dimension is None or not dimension.groupable or dimension.column is None:
        raise CompileError("group-by dimension is not approved / 分组维度未获批准")
    if not isinstance(definition.operation, AggregateOperation):
        raise CompileError("metric does not support grouping / 指标不支持分组")
    binding = definition.operation.filter_bindings.get(plan.group_by)
    if binding is None or binding.column != dimension.column:
        raise CompileError("group-by binding mismatch / 分组绑定不匹配")
    if plan.order not in {None, ORDER_METRIC_ASC, ORDER_METRIC_DESC}:
        raise CompileError("unsupported ranking order / 不支持的排名顺序")
    if plan.limit is not None and (
        isinstance(plan.limit, bool)
        or not isinstance(plan.limit, int)
        or not 1 <= plan.limit <= MAX_GROUPED_ROWS
    ):
        raise CompileError(
            f"ranking limit must be between 1 and {MAX_GROUPED_ROWS} / 排名数量超出范围"
        )
    if plan.order is None and plan.limit is not None:
        raise CompileError("limit requires ranking order / 限制数量需要排名顺序")
    if plan.order is not None and plan.limit is None:
        raise CompileError("ranking order requires limit / 排名顺序需要数量")


CompilerFunction = Callable[..., CompiledQuery]
STRATEGY_COMPILERS: Mapping[CompilerStrategy, CompilerFunction] = MappingProxyType(
    {
        CompilerStrategy.AGGREGATE: _compile_aggregate,
        CompilerStrategy.DIFFERENCE_OF_SUMS: _compile_difference,
    }
)


def compile_plan(
    plan: SemanticPlan, profile: DomainProfile | None = None
) -> CompiledQuery:
    """Compile only a validated SemanticPlan using finite operation templates."""
    if not isinstance(plan, SemanticPlan):
        raise CompileError("invalid semantic plan shape / 无效的语义计划形状")
    if plan.status != PLAN_READY or plan.metric is None:
        raise CompileError("semantic plan is not ready / 语义计划尚不可执行")
    selected = profile or load_default_profile()
    definition = selected.metric_catalog.get(plan.metric)
    if definition is None:
        raise CompileError(f"unsupported metric: {plan.metric} / 不支持的业务指标")
    if not isinstance(plan.filters, dict):
        raise CompileError("invalid filters shape / 无效的过滤条件形状")
    filters = _validated_filters(plan, definition, selected)
    _validate_analytics(plan, definition, selected)
    operation = definition.operation
    if isinstance(operation, AggregateOperation):
        return _compile_aggregate(definition, operation, filters, plan, selected)
    if isinstance(operation, DifferenceOfSumsOperation):
        if any(
            value is not None
            for value in (plan.time_range, plan.group_by, plan.order, plan.limit)
        ):
            raise CompileError("metric does not support analytics / 指标不支持分析字段")
        return _compile_difference(definition, operation, filters)
    raise CompileError(f"unsupported compiler operation: {type(operation).__name__}")
