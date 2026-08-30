from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from .verification import ResultContract


COUNT_INTENT = "__count_intent__"
NET_OF = "__net_of__"


class CompilerStrategy(str, Enum):
    """Finite internal compiler strategies; never catalog-provided SQL parts."""

    REVENUE = "REVENUE"
    COMPLETED_ORDER_COUNT = "COMPLETED_ORDER_COUNT"
    PENDING_ORDER_COUNT = "PENDING_ORDER_COUNT"
    AVG_COMPLETED_ORDER_VALUE = "AVG_COMPLETED_ORDER_VALUE"
    MAX_COMPLETED_ORDER_TOTAL = "MAX_COMPLETED_ORDER_TOTAL"
    COMPLETED_PAYMENT_SUM = "COMPLETED_PAYMENT_SUM"
    COMPLETED_REFUND_SUM = "COMPLETED_REFUND_SUM"


@dataclass(frozen=True)
class CompositionPattern:
    """Reusable semantic feature family for one governed metric."""

    required_feature_groups: tuple[frozenset[str], ...]


@dataclass(frozen=True)
class ResolverMetadata:
    canonical_forms: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    cjk_aliases: tuple[str, ...] = ()
    composition_patterns: tuple[CompositionPattern, ...] = ()


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    business_meaning: str
    resolver: ResolverMetadata
    result_contract: ResultContract
    compiler_strategy: CompilerStrategy
    allowed_filters: frozenset[str] = frozenset()


METRIC_DEFINITIONS = (
    MetricDefinition(
        metric_id="revenue",
        business_meaning=(
            "Completed payment amount minus completed refunds / "
            "已完成付款减已完成退款"
        ),
        resolver=ResolverMetadata(
            canonical_forms=("revenue",),
            aliases=("net revenue",),
            cjk_aliases=("收入", "营收"),
            composition_patterns=(
                CompositionPattern(
                    required_feature_groups=(
                        frozenset({"net"}),
                        frozenset({"sale"}),
                        frozenset({"refund"}),
                        frozenset({"after", "following", NET_OF}),
                    )
                ),
            ),
        ),
        result_contract=ResultContract.scalar_numeric("revenue"),
        compiler_strategy=CompilerStrategy.REVENUE,
        allowed_filters=frozenset({"region"}),
    ),
    MetricDefinition(
        metric_id="completed_orders",
        business_meaning="Count of completed orders / 已完成订单数量",
        resolver=ResolverMetadata(
            canonical_forms=("completed_orders", "completed orders"),
            aliases=("completed order count",),
            cjk_aliases=("订单数",),
            composition_patterns=(
                CompositionPattern(
                    required_feature_groups=(
                        frozenset({"completed", "finished"}),
                        frozenset({"order"}),
                        frozenset({COUNT_INTENT}),
                    )
                ),
            ),
        ),
        result_contract=ResultContract.scalar_numeric("completed_orders"),
        compiler_strategy=CompilerStrategy.COMPLETED_ORDER_COUNT,
        allowed_filters=frozenset({"region"}),
    ),
    MetricDefinition(
        metric_id="pending_orders",
        business_meaning="Count of pending orders / 待处理订单数量",
        resolver=ResolverMetadata(
            canonical_forms=("pending_orders", "pending orders"),
            aliases=("pending order count", "number of pending orders"),
            composition_patterns=(
                CompositionPattern(
                    required_feature_groups=(
                        frozenset({"pending"}),
                        frozenset({"order"}),
                        frozenset({COUNT_INTENT}),
                    )
                ),
            ),
        ),
        result_contract=ResultContract.scalar_numeric("pending_orders"),
        compiler_strategy=CompilerStrategy.PENDING_ORDER_COUNT,
    ),
    MetricDefinition(
        metric_id="max_completed_order_total",
        business_meaning=(
            "Maximum total amount among completed orders / "
            "已完成订单中的最高订单总额"
        ),
        resolver=ResolverMetadata(
            canonical_forms=("max_completed_order_total",),
            composition_patterns=(
                CompositionPattern(
                    required_feature_groups=(
                        frozenset({"highest", "maximum", "largest", "max"}),
                        frozenset({"completed", "finished"}),
                        frozenset({"order"}),
                        frozenset({"total", "amount", "value"}),
                    )
                ),
            ),
        ),
        result_contract=ResultContract.scalar_numeric(
            "max_completed_order_total"
        ),
        compiler_strategy=CompilerStrategy.MAX_COMPLETED_ORDER_TOTAL,
    ),
    MetricDefinition(
        metric_id="avg_order_value",
        business_meaning=(
            "Average total for completed orders / 已完成订单平均客单价"
        ),
        resolver=ResolverMetadata(
            canonical_forms=("avg_order_value", "average order value"),
            aliases=("aov",),
            cjk_aliases=("客单价",),
            composition_patterns=(
                CompositionPattern(
                    required_feature_groups=(
                        frozenset({"avg", "average", "mean"}),
                        frozenset({"order", "basket"}),
                        frozenset({"value", "amount"}),
                    )
                ),
            ),
        ),
        result_contract=ResultContract.scalar_numeric("avg_order_value"),
        compiler_strategy=CompilerStrategy.AVG_COMPLETED_ORDER_VALUE,
        allowed_filters=frozenset({"region"}),
    ),
    MetricDefinition(
        metric_id="completed_payments",
        business_meaning=(
            "Total amount of completed payments / 已完成付款总额"
        ),
        resolver=ResolverMetadata(
            canonical_forms=("completed_payments",),
            composition_patterns=(
                CompositionPattern(
                    required_feature_groups=(
                        frozenset({"completed"}),
                        frozenset({"payment"}),
                        frozenset({"gross", "total", "amount", "sum"}),
                    )
                ),
            ),
        ),
        result_contract=ResultContract.scalar_numeric("completed_payments"),
        compiler_strategy=CompilerStrategy.COMPLETED_PAYMENT_SUM,
    ),
    MetricDefinition(
        metric_id="completed_refunds",
        business_meaning="Total amount of completed refunds / 已完成退款总额",
        resolver=ResolverMetadata(
            canonical_forms=("completed_refunds",),
            composition_patterns=(
                CompositionPattern(
                    required_feature_groups=(
                        frozenset({"completed"}),
                        frozenset({"refund"}),
                        frozenset({"total", "amount", "sum"}),
                    )
                ),
            ),
        ),
        result_contract=ResultContract.scalar_numeric("completed_refunds"),
        compiler_strategy=CompilerStrategy.COMPLETED_REFUND_SUM,
    ),
)

_metric_ids = tuple(definition.metric_id for definition in METRIC_DEFINITIONS)
if len(_metric_ids) != len(set(_metric_ids)):
    raise RuntimeError("metric catalog ids must be unique")

METRIC_CATALOG = MappingProxyType(
    {definition.metric_id: definition for definition in METRIC_DEFINITIONS}
)
