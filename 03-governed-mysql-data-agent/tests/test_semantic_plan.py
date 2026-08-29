import pytest

from src.agent import DataAgent
from src.demo import initialize_demo
from src.semantic import (
    PLAN_NEEDS_CLARIFICATION,
    PLAN_READY,
    build_semantic_plan,
)


def test_canonical_revenue_plan_remains_executable():
    plan = build_semantic_plan("Please show the revenue metric")

    assert plan.status == PLAN_READY
    assert plan.metric == "revenue"
    assert plan.filters == {}


def test_configured_explicit_chinese_alias_remains_executable():
    plan = build_semantic_plan("请查询收入")

    assert plan.status == PLAN_READY
    assert plan.metric == "revenue"


def test_multiple_metrics_require_clarification():
    plan = build_semantic_plan("revenue or completed_orders")

    assert plan.status == PLAN_NEEDS_CLARIFICATION
    assert plan.metric is None
    assert "multiple business metrics" in plan.reason


def test_vague_scope_marker_requires_clarification_without_rejecting_all_short_inputs():
    vague = build_semantic_plan("查一下收入")
    explicit = build_semantic_plan("收入")

    assert vague.status == PLAN_NEEDS_CLARIFICATION
    assert vague.metric == "revenue"
    assert explicit.status == PLAN_READY
    assert explicit.metric == "revenue"


def test_supported_region_filter_is_preserved_compiled_and_executed(tmp_path):
    db_path = initialize_demo(tmp_path / "demo.db")

    result = DataAgent(db_path).answer("revenue for the north region")

    assert result["status"] == "OK"
    assert result["semantic_plan"]["metric"] == "revenue"
    assert result["semantic_plan"]["filters"] == {"region": "north"}
    assert result["params"] == ["north", "north"]
    assert "north" not in result["sql"]
    assert result["metric"] == "north_revenue"
    assert result["evidence"] == {"north_revenue": 0.0}
    assert result["verified"] is True


@pytest.mark.parametrize(
    ("region", "expected"),
    [("south", 0.0), ("east", 100.0)],
)
def test_region_revenue_compilation_generalizes_beyond_benchmark_case(
    region, expected, tmp_path
):
    db_path = initialize_demo(tmp_path / f"{region}.db")

    result = DataAgent(db_path).answer(f"revenue for the {region} region")

    result_metric = f"{region}_revenue"
    assert result["status"] == "OK"
    assert result["metric"] == result_metric
    assert result["evidence"] == {result_metric: expected}
    assert result["params"] == [region, region]


@pytest.mark.parametrize(
    "question",
    [
        "查一下收入",
        "收入还是订单数",
        "revenue or completed_orders",
    ],
)
def test_original_false_success_regressions_stop_before_sql(question, tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer(question)

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["trace"] == ["resolve_metric"]
    assert "evidence" not in result
    assert "verified" not in result
    assert not db_path.exists()


@pytest.mark.parametrize(
    "question",
    [
        "How much money did we make?",
        "What is the average basket value?",
    ],
)
def test_existing_synonym_safe_failures_do_not_execute_sql(question, tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer(question)

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["trace"] == ["resolve_metric"]
    assert "verified" not in result
    assert not db_path.exists()


def test_unseen_multiple_metric_wording_generalizes_to_clarification():
    plan = build_semantic_plan(
        "Could you compare avg_order_value against revenue for me?"
    )

    assert plan.status == PLAN_NEEDS_CLARIFICATION
    assert plan.metric is None
    assert "multiple business metrics" in plan.reason


def test_unseen_region_and_wording_use_the_same_compiler(tmp_path):
    db_path = initialize_demo(tmp_path / "demo.db")

    result = DataAgent(db_path).answer(
        "Kindly show completed_orders for the west region"
    )

    assert result["status"] == "OK"
    assert result["semantic_plan"]["metric"] == "completed_orders"
    assert result["semantic_plan"]["filters"] == {"region": "west"}
    assert result["params"] == ["west"]
    assert result["metric"] == "west_completed_orders"
    assert result["evidence"] == {"west_completed_orders": 1}
    assert result["verified"] is True


def test_unsupported_region_is_preserved_and_stops_before_database(tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer("revenue for the central region")

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["filters"] == {"region": "central"}
    assert result["trace"] == ["resolve_metric", "compile_query"]
    assert "sql" not in result
    assert "evidence" not in result
    assert "verified" not in result
    assert not db_path.exists()


def test_explicit_status_filter_is_preserved_but_rejected_before_database(tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer("completed_orders with status pending")

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["filters"] == {"status": "pending"}
    assert result["trace"] == ["resolve_metric", "compile_query"]
    assert "sql" not in result
    assert not db_path.exists()


def test_unseen_ambiguity_wording_uses_scope_condition_not_full_sentence(tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer("麻烦帮我查询一下营收数据")

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["metric"] == "revenue"
    assert result["semantic_plan"]["filters"] == {}
    assert result["trace"] == ["resolve_metric"]
    assert "verified" not in result
    assert not db_path.exists()


def test_unseen_single_metric_wording_remains_ready():
    plan = build_semantic_plan("Kindly return the completed_orders metric")

    assert plan.status == PLAN_READY
    assert plan.metric == "completed_orders"
    assert plan.filters == {}
