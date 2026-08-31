from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from src.compiler import CompileError, compile_plan
from src.policy import validate_sql
from src.profile import load_profile
from src.semantic import (
    ORDER_METRIC_DESC,
    PLAN_READY,
    DateRange,
    SemanticPlan,
    build_semantic_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE = load_profile(PROJECT_ROOT / "profiles" / "expenses.json")
REFERENCE_DATE = date(2026, 8, 31)


def _compile(question):
    return compile_plan(
        build_semantic_plan(question, PROFILE, REFERENCE_DATE), PROFILE
    )


def test_time_filter_uses_half_open_bound_parameters():
    compiled = _compile(
        "total expenses between 2026-08-01 and 2026-08-05"
    )

    assert compiled.sql == (
        "SELECT ROUND(COALESCE(SUM(amount),0),2) AS total_expenses "
        "FROM expenses WHERE spent_on>=? AND spent_on<?"
    )
    assert compiled.params == ("2026-08-01", "2026-08-06")
    assert validate_sql(compiled.sql) == (True, "ok")


def test_grouping_is_deterministic_and_uses_overflow_probe_limit():
    compiled = _compile("total expenses by category")

    assert compiled.sql == (
        "SELECT category AS category, "
        "ROUND(COALESCE(SUM(amount),0),2) AS total_expenses "
        "FROM expenses GROUP BY category ORDER BY category ASC LIMIT ?"
    )
    assert compiled.params == (101,)
    assert compiled.result_contract.dimension_key == "category"
    assert compiled.result_contract.max_rows == 100
    assert compiled.result_contract.requested_limit is None
    assert compiled.result_contract.order == "dimension_asc"
    assert validate_sql(compiled.sql) == (True, "ok")


def test_ranked_grouping_composes_filters_and_time_with_bound_limit():
    compiled = _compile(
        "top 3 expense categories for groceries this month"
    )

    assert compiled.sql == (
        "SELECT category AS category, "
        "ROUND(COALESCE(SUM(amount),0),2) AS total_expenses "
        "FROM expenses WHERE category=? AND spent_on>=? AND spent_on<? "
        "GROUP BY category ORDER BY total_expenses DESC, category ASC LIMIT ?"
    )
    assert compiled.params == ("food", "2026-08-01", "2026-09-01", 3)
    assert compiled.result_contract.requested_limit == 3
    assert compiled.result_contract.order == ORDER_METRIC_DESC
    assert validate_sql(compiled.sql) == (True, "ok")


def _ready_plan(**overrides):
    values = {
        "metric": "total_expenses",
        "filters": {},
        "status": PLAN_READY,
        "reason": "ready",
    }
    values.update(overrides)
    return SemanticPlan(**values)


@pytest.mark.parametrize(
    "plan",
    [
        _ready_plan(group_by="category;drop_table"),
        _ready_plan(group_by="category", order="random", limit=3),
        _ready_plan(group_by="category", order=ORDER_METRIC_DESC, limit=101),
        _ready_plan(group_by="category", order=ORDER_METRIC_DESC),
        _ready_plan(limit=3),
        _ready_plan(
            time_range=DateRange(
                "date;drop", date(2026, 8, 1), date(2026, 9, 1), "x"
            )
        ),
        _ready_plan(
            time_range=DateRange(
                "date", date(2026, 9, 1), date(2026, 8, 1), "x"
            )
        ),
    ],
)
def test_forged_analytics_plans_fail_closed(plan):
    with pytest.raises(CompileError):
        compile_plan(plan, PROFILE)


def test_compiler_revalidates_plan_even_if_frozen_instance_is_replaced():
    valid = build_semantic_plan(
        "top 3 expense categories", PROFILE, REFERENCE_DATE
    )

    with pytest.raises(CompileError, match="group-by"):
        compile_plan(replace(valid, group_by="merchant"), PROFILE)
