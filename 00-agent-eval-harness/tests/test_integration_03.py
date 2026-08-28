import json
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


def test_fixture_has_no_actual_and_rejects_a_precomputed_actual(tmp_path):
    cases = load_integration_cases(CASES_PATH)
    assert len(cases) == 10
    assert all("actual" not in case for case in cases)

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

    assert summary.total_cases == 10
    assert summary.outcome_success_rate == 1.0
    assert summary.evaluator_conformance_rate == 1.0
    assert summary.dimension_averages.state_score == 1.0
    assert summary.dimension_averages.policy_score == 1.0
    assert summary.dimension_averages.verification_score == 1.0
    assert summary.dimension_averages.overall_score == 1.0

    blocked = next(
        execution
        for execution in executions
        if execution.result.case_id == "03-policy-block-delete"
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
        if execution.result.case_id == "03-unknown-metric"
    )
    assert clarification.result.success is True
    assert clarification.result.verification.applicable is False

    normal = next(
        execution
        for execution in executions
        if execution.result.case_id == "03-revenue-en"
    )
    assert normal.result.required_dimensions == (
        "state",
        "policy",
        "verification",
    )
    assert normal.result.verification.applicable is True
    assert normal.result.verification.passed is True


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
    assert "No outcome failures were observed." in markdown
