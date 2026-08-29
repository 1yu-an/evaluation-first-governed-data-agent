import pytest

from src.agent import DataAgent
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


def test_unsupported_region_filter_is_preserved_and_blocks_execution(tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer("revenue for the north region")

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["metric"] == "revenue"
    assert result["semantic_plan"]["filters"] == {"region": "north"}
    assert result["trace"] == ["resolve_metric"]
    assert "sql" not in result
    assert "evidence" not in result
    assert "verified" not in result
    assert not db_path.exists()


@pytest.mark.parametrize(
    "question",
    [
        "查一下收入",
        "收入还是订单数",
        "revenue or completed_orders",
        "revenue for the north region",
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


def test_unseen_region_and_wording_preserve_filter_before_sql(tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer(
        "Kindly show completed_orders for the west region"
    )

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["metric"] == "completed_orders"
    assert result["semantic_plan"]["filters"] == {"region": "west"}
    assert result["trace"] == ["resolve_metric"]
    assert "verified" not in result
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
