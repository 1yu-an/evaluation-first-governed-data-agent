from pathlib import Path

import pytest

from src.agent import DataAgent
from src.compiler import CompileError, compile_plan
from src.demo import initialize_expenses
from src.profile import load_profile
from src.semantic import (
    PLAN_NEEDS_CLARIFICATION,
    PLAN_READY,
    SemanticPlan,
    build_semantic_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPENSES_PROFILE = load_profile(PROJECT_ROOT / "profiles" / "expenses.json")


@pytest.fixture
def expenses_agent(tmp_path):
    database = initialize_expenses(tmp_path / "expenses.db")
    return DataAgent(database, profile=EXPENSES_PROFILE)


@pytest.mark.parametrize(
    ("question", "metric", "value"),
    [
        ("total expenses", "total_expenses", 977.5),
        ("how many expenses", "expense_count", 6),
        ("average expense", "average_expense", 162.92),
        ("total expenses for groceries", "total_expenses", 47.5),
        ("expense count for transport", "expense_count", 2),
        ("average expense for housing", "average_expense", 900.0),
    ],
)
def test_non_demo_profile_answers_three_metrics_and_one_filter(
    expenses_agent, question, metric, value
):
    result = expenses_agent.answer(question)

    assert result["status"] == "OK"
    assert result["profile_id"] == "expenses"
    assert result["metric"] == metric
    assert result["value"] == value
    assert result["evidence"] == {metric: value}
    assert result["verified"] is True


def test_personal_filter_is_normalized_and_bound_not_interpolated(
    expenses_agent,
):
    result = expenses_agent.answer("total spending for groceries")

    assert result["filters"] == {"category": "food"}
    assert result["params"] == ["food"]
    assert result["sql"].endswith("WHERE category=?")
    assert "food" not in result["sql"]


def test_multi_category_and_unknown_questions_fail_before_execution(tmp_path):
    unopened = tmp_path / "must-not-be-opened.db"
    agent = DataAgent(unopened, profile=EXPENSES_PROFILE)

    ambiguous = agent.answer("total expenses for food and transport")
    unsupported = agent.answer("largest merchant")

    assert ambiguous["status"] == PLAN_NEEDS_CLARIFICATION
    assert unsupported["status"] == PLAN_NEEDS_CLARIFICATION
    assert ambiguous["trace"] == ["resolve_metric"]
    assert unsupported["trace"] == ["resolve_metric"]
    assert not unopened.exists()


def test_injection_shaped_filter_value_is_rejected_by_compiler():
    plan = SemanticPlan(
        metric="total_expenses",
        filters={"category": "food' OR 1=1 --"},
        status=PLAN_READY,
        reason="ready",
    )

    with pytest.raises(CompileError, match="unsupported category value"):
        compile_plan(plan, EXPENSES_PROFILE)


def test_explain_never_calls_executor():
    class ExplodingExecutor:
        name = "must-not-run"

        def execute(self, query):
            raise AssertionError("explain called executor")

    agent = DataAgent(executor=ExplodingExecutor(), profile=EXPENSES_PROFILE)

    result = agent.explain("average expense for transport")

    assert result["status"] == "OK"
    assert result["executed"] is False
    assert result["parameter_style"] == "qmark"
    assert result["params"] == ["transport"]
    assert result["trace"] == [
        "resolve_metric",
        "compile_query",
        "validate_sql",
    ]


def test_expenses_resolver_is_selected_without_core_source_changes():
    plan = build_semantic_plan("mean expense for transit", EXPENSES_PROFILE)

    assert plan.status == PLAN_READY
    assert plan.metric == "average_expense"
    assert plan.filters == {"category": "transport"}
