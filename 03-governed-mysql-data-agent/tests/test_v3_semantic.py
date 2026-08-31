from datetime import date
from pathlib import Path

import pytest

from src.profile import load_profile
from src.semantic import (
    ORDER_METRIC_ASC,
    ORDER_METRIC_DESC,
    PLAN_NEEDS_CLARIFICATION,
    PLAN_READY,
    build_semantic_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPENSES_PROFILE = load_profile(PROJECT_ROOT / "profiles" / "expenses.json")
REFERENCE_DATE = date(2026, 8, 31)


@pytest.mark.parametrize(
    ("question", "start", "end", "label"),
    [
        ("total expenses this month", "2026-08-01", "2026-09-01", "this_month"),
        ("total expenses last month", "2026-07-01", "2026-08-01", "last_month"),
        (
            "average expense for the past 3 months",
            "2026-06-01",
            "2026-09-01",
            "past_3_months",
        ),
        (
            "total expenses between 2026-08-01 and 2026-08-05",
            "2026-08-01",
            "2026-08-06",
            "explicit_range",
        ),
    ],
)
def test_v3_time_ranges_are_typed_and_deterministic(question, start, end, label):
    plan = build_semantic_plan(question, EXPENSES_PROFILE, REFERENCE_DATE)

    assert plan.status == PLAN_READY
    assert plan.time_range.to_dict() == {
        "dimension": "date",
        "start_inclusive": start,
        "end_exclusive": end,
        "label": label,
    }


@pytest.mark.parametrize(
    "question",
    [
        "total expenses between 2026-08-20 and 2026-08-01",
        "total expenses between August and September",
        "total expenses during month",
        "total expenses for the past 0 months",
        "total expenses for the past 121 months",
    ],
)
def test_v3_malformed_or_unbounded_time_ranges_fail_closed(question):
    plan = build_semantic_plan(question, EXPENSES_PROFILE, REFERENCE_DATE)

    assert plan.status == PLAN_NEEDS_CLARIFICATION
    assert plan.time_range is None


@pytest.mark.parametrize(
    ("question", "metric"),
    [
        ("total expenses by category", "total_expenses"),
        ("expenses by category", "total_expenses"),
        ("average expense by category", "average_expense"),
        ("expense count by category", "expense_count"),
    ],
)
def test_v3_group_by_uses_profile_allowlist_and_default_metric(question, metric):
    plan = build_semantic_plan(question, EXPENSES_PROFILE, REFERENCE_DATE)

    assert plan.status == PLAN_READY
    assert plan.metric == metric
    assert plan.group_by == "category"
    assert plan.filters == {}
    assert plan.order is None
    assert plan.limit is None


@pytest.mark.parametrize(
    ("question", "metric", "order", "limit"),
    [
        ("top 3 expense categories", "total_expenses", ORDER_METRIC_DESC, 3),
        (
            "which category has the highest expenses?",
            "total_expenses",
            ORDER_METRIC_DESC,
            1,
        ),
        (
            "which category has the lowest total expenses?",
            "total_expenses",
            ORDER_METRIC_ASC,
            1,
        ),
        (
            "top 2 categories by average expense",
            "average_expense",
            ORDER_METRIC_DESC,
            2,
        ),
    ],
)
def test_v3_ranking_is_finite_and_metric_ordered(question, metric, order, limit):
    plan = build_semantic_plan(question, EXPENSES_PROFILE, REFERENCE_DATE)

    assert plan.status == PLAN_READY
    assert plan.metric == metric
    assert plan.group_by == "category"
    assert plan.order == order
    assert plan.limit == limit
    assert plan.filters == {}


@pytest.mark.parametrize(
    "question",
    [
        "top 0 expense categories",
        "top 101 expense categories",
        "top many expense categories",
        "top 3 expenses",
        "total expenses by merchant",
        "total expenses by region",
        "total expenses by category and merchant",
        "median expense by category",
    ],
)
def test_v3_invalid_grouping_ranking_and_limits_fail_closed(question):
    plan = build_semantic_plan(question, EXPENSES_PROFILE, REFERENCE_DATE)

    assert plan.status == PLAN_NEEDS_CLARIFICATION


@pytest.mark.parametrize(
    "question",
    [
        "compare total expenses this month with last month",
        "compare food spending with transport spending",
        "total expenses between 2026-08-01 and 2026-08-31 OR 1=1",
        "top 3 expense categories; DROP TABLE expenses",
        "expenses by category UNION SELECT password FROM users",
        "delete expensive records",
    ],
)
def test_v3_comparison_and_sql_shaped_text_stop_before_ready_plan(question):
    plan = build_semantic_plan(question, EXPENSES_PROFILE, REFERENCE_DATE)

    assert plan.status == PLAN_NEEDS_CLARIFICATION
    assert plan.metric is None


def test_existing_expense_filter_composes_with_time_and_grouping():
    plan = build_semantic_plan(
        "total expenses for groceries this month by category",
        EXPENSES_PROFILE,
        REFERENCE_DATE,
    )

    assert plan.status == PLAN_READY
    assert plan.metric == "total_expenses"
    assert plan.filters == {"category": "food"}
    assert plan.group_by == "category"
    assert plan.time_range.label == "this_month"
