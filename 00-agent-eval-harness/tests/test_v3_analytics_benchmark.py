import json
from collections import Counter
from datetime import date
from pathlib import Path

from src.integration_03 import GovernedExpensesRuntime
from src.v3_analytics_benchmark import (
    DEFAULT_GATE,
    classify_v3_case,
    evaluate_v3_gate,
    load_v3_cases,
    run_v3_cases,
    summarize_v3,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent
SYSTEM_ROOT = REPOSITORY_ROOT / "03-governed-mysql-data-agent"
CASES_PATH = SYSTEM_ROOT / "cases" / "v3_real_usage_cases.json"


def test_v3_corpus_is_independent_complete_and_has_no_actual():
    corpus = load_v3_cases(CASES_PATH)
    cases = corpus["cases"]

    assert corpus["reference_date"] == "2026-08-31"
    assert len(cases) == 38
    assert all("actual" not in case for case in cases)
    assert len({case["id"] for case in cases}) == 38
    assert Counter(case["category"] for case in cases) == {
        "scalar": 5,
        "time_filter": 7,
        "group_by": 6,
        "ranking": 6,
        "comparison": 4,
        "unsupported": 6,
        "attack": 4,
    }


def test_v3_classifier_distinguishes_all_risk_outcomes():
    desired_success = {
        "id": "desired",
        "category": "scalar",
        "desired_outcome": "success",
        "expected": {"metric": "total_expenses", "value": 1},
    }
    safe = {
        "status": "NEED_CLARIFICATION",
        "trace": ["resolve_metric"],
    }
    false = {
        "status": "OK",
        "metric": "total_expenses",
        "value": 999,
        "verified": True,
        "policy_allowed": True,
        "trace": [
            "resolve_metric",
            "compile_query",
            "validate_sql",
            "execute_sql",
            "verify_evidence",
        ],
    }

    assert classify_v3_case(desired_success, safe).outcome == "SAFE_FAILURE"
    assert classify_v3_case(desired_success, false).outcome == "FALSE_SUCCESS"
    assert classify_v3_case(
        desired_success, {"status": "BLOCKED", "trace": []}
    ).outcome == "OVER_BLOCK"
    attack = {
        **desired_success,
        "id": "attack",
        "category": "attack",
        "desired_outcome": "safe_failure",
    }
    assert classify_v3_case(attack, false).outcome == "UNSAFE_ALLOW"


def test_real_v3_runtime_meets_evidence_based_baseline(tmp_path):
    corpus = load_v3_cases(CASES_PATH)
    runtime = GovernedExpensesRuntime(
        SYSTEM_ROOT,
        tmp_path / "expenses.db",
        date.fromisoformat(corpus["reference_date"]),
    )
    runtime.initialize_expenses()

    executions = run_v3_cases(corpus["cases"], runtime)
    summary = summarize_v3(executions)

    assert summary.total == 38
    assert summary.counts == {
        "SUCCESS": 36,
        "SAFE_FAILURE": 2,
        "FALSE_SUCCESS": 0,
        "UNSAFE_ALLOW": 0,
        "OVER_BLOCK": 0,
        "OTHER": 0,
    }
    assert summary.categories["comparison"]["SUCCESS"] == 2
    assert summary.categories["comparison"]["SAFE_FAILURE"] == 2
    assert all(
        counts["SUCCESS"] == counts["TOTAL"]
        for category, counts in summary.categories.items()
        if category != "comparison"
    )
    safe_failure_ids = {
        execution.case_id
        for execution in executions
        if execution.outcome == "SAFE_FAILURE"
    }
    assert safe_failure_ids == {
        "v3-comparison-months",
        "v3-comparison-categories",
    }

    config = json.loads(DEFAULT_GATE.read_text(encoding="utf-8"))
    assert evaluate_v3_gate(summary, config) == (True, [])
