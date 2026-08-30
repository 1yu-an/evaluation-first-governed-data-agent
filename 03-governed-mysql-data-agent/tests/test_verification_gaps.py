import sqlite3
from unittest.mock import patch

import pytest

from src.agent import DataAgent
from src.compiler import CompiledQuery, compile_plan
from src.demo import initialize_demo
from src.semantic import build_semantic_plan
from src.verification import ResultContract


class StaticEvidenceExecutor:
    name = "adversarial-static"

    def __init__(self, evidence):
        self.evidence = evidence

    def execute(self, query):
        return self.evidence


def test_result_contract_cannot_prove_wrong_metric_sql(tmp_path):
    db_path = initialize_demo(tmp_path / "wrong-metric.db")
    wrong_query = CompiledQuery(
        sql=(
            "SELECT COUNT(*) AS revenue FROM orders "
            "WHERE status='completed'"
        ),
        result_metric="revenue",
        result_contract=ResultContract.scalar_numeric("revenue"),
    )

    with patch("src.agent.compile_plan", return_value=wrong_query):
        result = DataAgent(db_path).answer("revenue")

    assert result["evidence"] == {"revenue": 2}
    assert result["verified"] is True


def test_result_contract_cannot_prove_sql_applied_scope(tmp_path):
    db_path = initialize_demo(tmp_path / "wrong-scope.db")
    unfiltered_sql = compile_plan(build_semantic_plan("revenue")).sql
    unfiltered_query = CompiledQuery(
        sql=unfiltered_sql,
        result_metric="north_revenue",
        result_contract=ResultContract.scalar_numeric("north_revenue"),
    )

    with patch("src.agent.compile_plan", return_value=unfiltered_query):
        result = DataAgent(db_path).answer("revenue for the north region")

    assert result["semantic_plan"]["filters"] == {"region": "north"}
    assert result["params"] == []
    assert result["evidence"] == {"north_revenue": 180.0}
    assert result["verified"] is True


def test_result_contract_cannot_prove_sql_aggregation(tmp_path):
    db_path = initialize_demo(tmp_path / "wrong-aggregation.db")
    wrong_query = CompiledQuery(
        sql=(
            "SELECT SUM(total) AS avg_order_value FROM orders "
            "WHERE status='completed'"
        ),
        result_metric="avg_order_value",
        result_contract=ResultContract.scalar_numeric("avg_order_value"),
    )

    with patch("src.agent.compile_plan", return_value=wrong_query):
        result = DataAgent(db_path).answer("avg_order_value")

    assert result["evidence"] == {"avg_order_value": 200.0}
    assert result["verified"] is True


@pytest.mark.parametrize(
    "bad_value",
    [[], {}, "180", True, None, float("nan"), float("inf"), float("-inf")],
)
def test_malformed_numeric_evidence_fails_closed(bad_value):
    result = DataAgent(
        executor=StaticEvidenceExecutor({"revenue": bad_value})
    ).answer("revenue")

    assert result["status"] == "ERROR"
    assert result["verified"] is False
    assert "evidence" not in result


def test_empty_evidence_fails_closed():
    result = DataAgent(executor=StaticEvidenceExecutor({})).answer("revenue")

    assert result["status"] == "ERROR"
    assert result["verified"] is False
    assert "evidence" not in result


def test_unexpected_evidence_field_fails_closed():
    result = DataAgent(
        executor=StaticEvidenceExecutor(
            {"revenue": 180.0, "unexpected_debug_field": "not business evidence"}
        )
    ).answer("revenue")

    assert result["status"] == "ERROR"
    assert result["verified"] is False
    assert "evidence" not in result


def test_multiple_rows_fail_closed_instead_of_being_truncated(tmp_path):
    db_path = initialize_demo(tmp_path / "multiple-rows.db")
    multirow_query = CompiledQuery(
        sql=(
            "SELECT total AS revenue FROM orders "
            "WHERE status='completed' ORDER BY id"
        ),
        result_metric="revenue",
        result_contract=ResultContract.scalar_numeric("revenue"),
    )
    with sqlite3.connect(db_path) as connection:
        source_rows = connection.execute(multirow_query.sql).fetchall()

    with patch("src.agent.compile_plan", return_value=multirow_query):
        result = DataAgent(db_path).answer("revenue")

    assert source_rows == [(120.0,), (80.0,)]
    assert result["status"] == "ERROR"
    assert "more than one" in result["reason"]
    assert "evidence" not in result
    assert "verified" not in result


def test_max_empty_completed_order_set_returns_null_and_fails_closed(tmp_path):
    db_path = initialize_demo(tmp_path / "empty-completed-orders.db")
    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE orders SET status='pending'")

    result = DataAgent(db_path).answer("highest completed order total")

    assert result["status"] == "ERROR"
    assert result["metric"] == "max_completed_order_total"
    assert "MAX(total)" in result["sql"]
    assert "COALESCE" not in result["sql"]
    assert result["verification"]["passed"] is False
    assert result["verification"]["reason"] == "result value must be non-null"
    assert result["verified"] is False
    assert "evidence" not in result


@pytest.mark.parametrize(
    ("question", "expected_evidence"),
    [
        ("revenue", {"revenue": 180.0}),
        ("completed_orders", {"completed_orders": 2}),
        ("avg_order_value", {"avg_order_value": 100.0}),
        (
            "highest completed order total",
            {"max_completed_order_total": 120.0},
        ),
        ("revenue for the north region", {"north_revenue": 0.0}),
    ],
)
def test_valid_scalar_numeric_evidence_still_verifies(
    question, expected_evidence, tmp_path
):
    db_path = initialize_demo(tmp_path / "valid-evidence.db")

    result = DataAgent(db_path).answer(question)

    assert result["status"] == "OK"
    assert result["evidence"] == expected_evidence
    assert result["verified"] is True
