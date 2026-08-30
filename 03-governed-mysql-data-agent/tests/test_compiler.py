import pytest

from src.compiler import CompileError, compile_plan
from src.policy import validate_sql
from src.semantic import PLAN_READY, SemanticPlan, build_semantic_plan


def _ready_plan(metric="revenue", filters=None):
    return SemanticPlan(
        metric=metric,
        filters={} if filters is None else filters,
        status=PLAN_READY,
        reason="ready / 可执行",
    )


def test_revenue_without_filters_preserves_the_canonical_query():
    compiled = compile_plan(_ready_plan())

    assert compiled.params == ()
    assert compiled.result_metric == "revenue"
    assert compiled.result_contract.expected_key == "revenue"
    assert compiled.result_contract.expected_type == "numeric"
    assert compiled.result_contract.nullable is False
    assert compiled.result_contract.cardinality == "exactly_one"
    assert compiled.sql == (
        "SELECT ROUND(COALESCE((SELECT SUM(amount) FROM payments "
        "WHERE status='completed'),0) - COALESCE((SELECT SUM(amount) "
        "FROM refunds WHERE status='completed'),0),2) AS revenue"
    )


@pytest.mark.parametrize(
    ("metric", "aggregation"),
    [
        ("completed_orders", "COUNT(*) AS completed_orders"),
        ("avg_order_value", "AVG(total)"),
    ],
)
def test_metric_uses_its_declared_aggregation(metric, aggregation):
    compiled = compile_plan(_ready_plan(metric))

    assert aggregation in compiled.sql
    assert compiled.result_metric == metric


@pytest.mark.parametrize("region", ["north", "south", "east"])
def test_region_filter_is_parameterized_by_the_generic_metric_compiler(region):
    compiled = compile_plan(_ready_plan(filters={"region": region}))

    assert "region=?" in compiled.sql
    assert region not in compiled.sql
    assert compiled.params == (region, region)
    assert compiled.result_metric == f"{region}_revenue"


def test_unsupported_filter_field_fails_instead_of_dropping_the_filter():
    with pytest.raises(CompileError, match="unsupported filter field"):
        compile_plan(_ready_plan(filters={"status": "pending"}))


@pytest.mark.parametrize(
    "filters",
    [
        {"region": "central"},
        {"region": "north' OR 1=1 --"},
        {"region": ["north"]},
    ],
)
def test_unsupported_region_value_or_shape_fails_closed(filters):
    with pytest.raises(CompileError, match="unsupported region"):
        compile_plan(_ready_plan(filters=filters))


def test_compiled_filtered_sql_still_passes_ast_policy():
    compiled = compile_plan(
        build_semantic_plan("revenue for the north region")
    )

    assert validate_sql(compiled.sql) == (True, "ok")


def test_all_existing_metrics_use_the_same_region_filter_contract():
    for metric in ("revenue", "completed_orders", "avg_order_value"):
        compiled = compile_plan(_ready_plan(metric, {"region": "west"}))

        assert "region=?" in compiled.sql
        assert compiled.params
        assert set(compiled.params) == {"west"}
        assert compiled.result_metric == f"west_{metric}"
