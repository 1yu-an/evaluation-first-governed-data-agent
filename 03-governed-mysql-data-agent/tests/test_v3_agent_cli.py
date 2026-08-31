import json
from datetime import date
from pathlib import Path

import pytest

from src.agent import DataAgent
from src.cli import main
from src.demo import initialize_expenses
from src.profile import load_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE = load_profile(PROJECT_ROOT / "profiles" / "expenses.json")
REFERENCE_DATE = date(2026, 8, 31)


@pytest.fixture
def agent(tmp_path):
    database = initialize_expenses(tmp_path / "expenses.db")
    return DataAgent(
        database, profile=PROFILE, reference_date=REFERENCE_DATE
    )


@pytest.mark.parametrize(
    ("question", "value"),
    [
        ("total expenses this month", 977.5),
        ("total expenses last month", 0),
        ("total expenses between 2026-08-01 and 2026-08-05", 50.5),
        ("expense count between 2026-08-01 and 2026-08-05", 3),
        ("average expense for the past 3 months", 162.92),
    ],
)
def test_time_filtered_scalar_answers_are_verified(agent, question, value):
    result = agent.answer(question)

    assert result["status"] == "OK"
    assert result["result_type"] == "scalar"
    assert result["value"] == value
    assert result["verified"] is True
    assert "spent_on>=?" in result["sql"]
    assert "spent_on<?" in result["sql"]


def test_grouped_answer_is_ordered_and_verified(agent):
    result = agent.answer("total expenses by category")

    assert result["status"] == "OK"
    assert result["result_type"] == "grouped"
    assert result["group_by"] == "category"
    assert result["order"] is None
    assert result["limit"] is None
    assert result["rows"] == [
        {"category": "food", "total_expenses": 47.5},
        {"category": "housing", "total_expenses": 900.0},
        {"category": "transport", "total_expenses": 30.0},
    ]
    assert result["row_count"] == 3
    assert result["verified"] is True


@pytest.mark.parametrize(
    ("question", "rows"),
    [
        (
            "top 2 expense categories",
            [
                {"category": "housing", "total_expenses": 900.0},
                {"category": "food", "total_expenses": 47.5},
            ],
        ),
        (
            "which category has the lowest total expenses?",
            [{"category": "transport", "total_expenses": 30.0}],
        ),
        (
            "top 2 categories by average expense",
            [
                {"category": "housing", "average_expense": 900.0},
                {"category": "food", "average_expense": 15.83},
            ],
        ),
    ],
)
def test_ranked_answers_are_metric_ordered_and_limited(agent, question, rows):
    result = agent.answer(question)

    assert result["status"] == "OK"
    assert result["rows"] == rows
    assert result["row_count"] == len(rows)
    assert result["limit"] == len(rows)
    assert result["verified"] is True


def test_explain_exposes_typed_plan_and_grouped_contract_without_execution(agent):
    result = agent.explain("top 3 expense categories this month")

    assert result["status"] == "OK"
    assert result["executed"] is False
    assert result["semantic_plan"]["time_range"]["label"] == "this_month"
    assert result["semantic_plan"]["group_by"] == "category"
    assert result["result_contract"] == {
        "cardinality": "grouped",
        "expected_key": "total_expenses",
        "dimension_key": "category",
        "max_rows": 100,
        "requested_limit": 3,
        "order": "metric_desc",
    }


def test_cli_grouped_output_is_concise_and_multirow(
    tmp_path, capsys, monkeypatch
):
    database = initialize_expenses(tmp_path / "expenses.db")
    monkeypatch.setenv("DATA_AGENT_EXECUTOR", "sqlite")

    exit_code = main(
        [
            "ask",
            "--profile",
            "profiles/expenses.json",
            "--db-path",
            str(database),
            "top 2 expense categories",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert result["status"] == "success"
    assert result["result_type"] == "grouped"
    assert result["rows"] == [
        {"category": "housing", "total_expenses": 900.0},
        {"category": "food", "total_expenses": 47.5},
    ]
    assert result["evidence"] == {
        "row_count": 2,
        "result_key": "total_expenses",
        "dimension_key": "category",
    }
    assert "sql" not in result


@pytest.mark.parametrize(
    ("question", "reason_code"),
    [
        ("compare food spending with transport spending", "unsupported_comparison"),
        ("total expenses by merchant", "unsupported_grouping"),
        ("top 101 expense categories", "invalid_ranking"),
        (
            "total expenses between 2026-08-20 and 2026-08-01",
            "invalid_time_filter",
        ),
        ("top 3 expense categories; DROP TABLE expenses", "unsafe_input"),
    ],
)
def test_cli_v3_safe_failures_have_specific_reason_codes(
    question, reason_code, capsys, monkeypatch
):
    monkeypatch.setenv("DATA_AGENT_EXECUTOR", "sqlite")

    exit_code = main(
        ["ask", "--profile", "profiles/expenses.json", question]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert result["status"] == "safe_failure"
    assert result["reason_code"] == reason_code
    assert result["evidence"] == {}
