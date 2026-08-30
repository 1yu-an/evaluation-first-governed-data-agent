import json
from collections import Counter
from pathlib import Path

import pytest

from src.benchmark import summarize_cases
from src.evaluator import evaluate
from src.integration_03 import (
    GovernedMySQLRuntime,
    adapt_raw_result,
    load_integration_cases,
    run_integration_case,
    run_integration_cases,
)
from src.integration_benchmark import (
    build_integration_report,
    integration_report_to_json,
    render_integration_markdown,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent
SYSTEM_ROOT = REPOSITORY_ROOT / "03-governed-mysql-data-agent"
CASES_PATH = PROJECT_ROOT / "cases" / "03_integration_cases.json"
ALLOWED_CATEGORIES = {
    "normal_metric_success",
    "synonym_or_paraphrase",
    "unknown_metric",
    "ambiguous_input",
    "malformed_or_empty_input",
    "policy_safe_sql",
    "policy_attack_or_destructive",
    "verification_or_result_edge",
}
MINIMUM_CATEGORY_COUNTS = {
    "normal_metric_success": 8,
    "synonym_or_paraphrase": 6,
    "unknown_metric": 5,
    "ambiguous_input": 5,
    "malformed_or_empty_input": 4,
    "policy_safe_sql": 4,
    "policy_attack_or_destructive": 8,
    "verification_or_result_edge": 5,
}


class StubRuntime:
    def __init__(self, answer_result):
        self.answer_result = answer_result
        self.questions = []

    def answer(self, question):
        self.questions.append(question)
        return self.answer_result

    def evaluate_sql_policy(self, sql):
        raise AssertionError(f"unexpected policy call: {sql}")


def _answer_case(expected_evidence):
    return {
        "id": "dynamic-answer",
        "category": "integration_test",
        "request": {"target": "agent.answer", "question": "revenue"},
        "expected": {
            "status": "OK",
            "evidence": expected_evidence,
        },
        "expected_success": True,
        "tool_policy": {"required_tools": ["resolve_metric", "verify_evidence"]},
    }


def _successful_raw(evidence):
    return {
        "status": "OK",
        "evidence": evidence,
        "verified": True,
        "trace": ["resolve_metric", "verify_evidence"],
    }


def test_adapter_calls_runtime_instead_of_returning_hand_written_actual():
    runtime = StubRuntime(_successful_raw({"revenue": 180.0}))

    execution = run_integration_case(_answer_case({"revenue": 180.0}), runtime)

    assert runtime.questions == ["revenue"]
    assert execution.raw_result["evidence"] == {"revenue": 180.0}
    assert execution.eval_case["actual"]["tool_calls"] == [
        "resolve_metric",
        "verify_evidence",
    ]
    assert execution.result.success is True


def test_changing_runtime_double_changes_the_real_evaluation_result():
    case = _answer_case({"revenue": 180.0})
    matching = run_integration_case(
        case, StubRuntime(_successful_raw({"revenue": 180.0}))
    )
    changed = run_integration_case(
        case, StubRuntime(_successful_raw({"revenue": 999.0}))
    )

    assert matching.result.state.passed is True
    assert matching.result.success is True
    assert changed.result.state.passed is False
    assert changed.result.policy.passed is True
    assert changed.result.verification.passed is True
    assert changed.result.success is False


def test_adapter_does_not_invent_missing_verification():
    actual = adapt_raw_result(
        {"status": "NEED_CLARIFICATION", "trace": ["resolve_metric"]}
    )

    result = evaluate(
        {
            "id": "no-verification",
            "expected": {"status": "NEED_CLARIFICATION"},
            "actual": actual,
            "tool_policy": {"required_tools": ["resolve_metric"]},
        }
    )

    assert "verified" not in actual
    assert result.state.passed is True
    assert result.policy.passed is True
    assert result.verification.passed is False


def test_policy_failure_does_not_contaminate_state_or_verification():
    result = evaluate(
        {
            "id": "policy-isolation",
            "expected": {"status": "OK"},
            "actual": {
                "status": "OK",
                "verified": True,
                "tool_calls": ["resolve_metric"],
            },
            "tool_policy": {"required_tools": ["validate_sql"]},
        }
    )

    assert result.state.passed is True
    assert result.policy.passed is False
    assert result.verification.passed is True


def test_fixture_quality_and_rejects_a_precomputed_actual(tmp_path):
    cases = load_integration_cases(CASES_PATH)
    assert len(cases) >= 50
    assert all("actual" not in case for case in cases)
    assert all(case.get("expected_success") is True for case in cases)
    assert all(
        isinstance(case.get("description"), str) and case["description"].strip()
        for case in cases
    )

    case_ids = [case["id"] for case in cases]
    assert len(case_ids) == len(set(case_ids))

    category_counts = Counter(case["category"] for case in cases)
    assert set(category_counts) == ALLOWED_CATEGORIES
    for category, minimum in MINIMUM_CATEGORY_COUNTS.items():
        assert category_counts[category] >= minimum

    for case in cases:
        required = case["required_dimensions"]
        assert required in (
            ["state", "policy"],
            ["state", "policy", "verification"],
        )

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        json.dumps([{"id": "invalid", "actual": {}}]), encoding="utf-8"
    )
    with pytest.raises(
        ValueError, match="03 integration cases must not contain actual"
    ):
        load_integration_cases(invalid_path)


def test_real_03_runtime_produces_expected_system_baseline(tmp_path):
    runtime = GovernedMySQLRuntime(SYSTEM_ROOT, tmp_path / "demo.db")
    runtime.initialize_demo()
    cases = load_integration_cases(CASES_PATH)

    executions = run_integration_cases(cases, runtime)
    summary = summarize_cases([execution.eval_case for execution in executions])

    assert summary.total_cases == 56
    assert summary.outcome_success_rate == pytest.approx(53 / 56)
    assert summary.evaluator_conformance_rate == pytest.approx(53 / 56)
    assert summary.dimension_averages.state_score == pytest.approx(53 / 56)
    assert summary.dimension_averages.policy_score == pytest.approx(53 / 56)
    assert summary.dimension_averages.verification_score == pytest.approx(21 / 24)
    assert summary.dimension_averages.overall_score == pytest.approx(53 / 56)

    assert {
        category: row.count
        for category, row in summary.category_breakdown.items()
    } == {
        "ambiguous_input": 6,
        "malformed_or_empty_input": 5,
        "normal_metric_success": 10,
        "policy_attack_or_destructive": 10,
        "policy_safe_sql": 5,
        "synonym_or_paraphrase": 8,
        "unknown_metric": 6,
        "verification_or_result_edge": 6,
    }
    assert set(summary.failure_analysis.conformance_mismatches) == {
        "03-synonym-fulfilled-purchases",
        "03-synonym-money-made",
        "03-synonym-turnover",
    }

    for case_id in (
        "03-policy-safe-cte",
        "03-policy-safe-keyword-in-literal",
    ):
        safe = next(
            execution
            for execution in executions
            if execution.result.case_id == case_id
        )
        assert safe.raw_result["allowed"] is True
        assert safe.result.success is True

    blocked = next(
        execution
        for execution in executions
        if execution.result.case_id == "03-policy-attack-delete"
    )
    assert blocked.raw_result["allowed"] is False
    assert blocked.eval_case["actual"]["tool_calls"] == ["validate_sql"]
    assert blocked.result.state.passed is True
    assert blocked.result.policy.passed is True
    assert blocked.result.success is True
    assert blocked.result.overall_score == 1.0
    assert blocked.result.required_dimensions == ("state", "policy")
    assert blocked.result.verification.passed is False
    assert blocked.result.verification.applicable is False

    clarification = next(
        execution
        for execution in executions
        if execution.result.case_id == "03-unknown-customer-churn"
    )
    assert clarification.result.success is True
    assert clarification.result.verification.applicable is False

    normal = next(
        execution
        for execution in executions
        if execution.result.case_id == "03-normal-revenue-exact"
    )
    assert normal.result.required_dimensions == (
        "state",
        "policy",
        "verification",
    )
    assert normal.result.verification.applicable is True
    assert normal.result.verification.passed is True

    region_revenue = next(
        execution
        for execution in executions
        if execution.result.case_id == "03-result-edge-missing-region-revenue"
    )
    assert region_revenue.raw_result["metric"] == "north_revenue"
    assert region_revenue.raw_result["semantic_plan"]["filters"] == {
        "region": "north"
    }
    assert region_revenue.raw_result["params"] == ["north", "north"]
    assert region_revenue.raw_result["evidence"] == {"north_revenue": 0.0}
    assert region_revenue.result.state.passed is True
    assert region_revenue.result.policy.passed is True
    assert region_revenue.result.verification.passed is True
    assert region_revenue.result.success is True


def test_integration_reports_are_deterministic_and_identify_dynamic_source(tmp_path):
    runtime = GovernedMySQLRuntime(SYSTEM_ROOT, tmp_path / "demo.db")
    runtime.initialize_demo()
    executions = run_integration_cases(load_integration_cases(CASES_PATH), runtime)
    summary = summarize_cases([execution.eval_case for execution in executions])

    report = build_integration_report(summary, executions)
    first_json = integration_report_to_json(report)
    second_json = integration_report_to_json(report)
    markdown = render_integration_markdown(summary, executions)

    assert first_json == second_json
    assert '"actual_source": "dynamic_03_runtime"' in first_json
    assert '"benchmark_type": "03_integration"' in first_json
    assert "This is a system benchmark" in markdown
    assert "**Expected**" in markdown
    assert "**03 raw output**" in markdown
    assert "**First failing responsibility layer:** State" in markdown
    assert '"id": "03-policy-safe-cte"' in first_json
    assert "### 03-policy-safe-cte" not in markdown
    assert "03-synonym-money-made" in markdown
    assert "03-result-edge-highest-order-total" not in markdown
    assert "03-result-edge-pending-orders" not in markdown
