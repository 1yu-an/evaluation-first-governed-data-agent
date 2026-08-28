from src.evaluator import DimensionResult, EvalResult, evaluate
from src.reporter import render_markdown_report


def _dimension(score, passed, reason):
    return DimensionResult(score=score, passed=passed, reason=reason)


def test_markdown_report_contains_summary_and_cases_table():
    report = render_markdown_report(
        [
            EvalResult(
                "ok",
                _dimension(1.0, True, "state matches expected / 状态符合预期"),
                _dimension(1.0, True, "no policy violation / 无策略违规"),
                _dimension(1.0, True, "verified / 已验证"),
                category="normal_success",
            ),
            EvalResult(
                "bad",
                _dimension(0.0, False, "final state mismatch / 最终状态不匹配"),
                _dimension(0.0, False, "policy violation / 策略违规"),
                _dimension(1.0, True, "verified / 已验证"),
                category="policy_violation",
            ),
        ],
        title="Demo Report",
    )

    assert "# Demo Report" in report
    assert "- Total cases: 2" in report
    assert "- Passed: 1" in report
    assert "- Failed: 1" in report
    assert "- Average score: 0.60" in report
    assert "| case_id | category | score | success | reason |" in report
    assert "| ok | normal_success | 1.0 | True | pass / 通过 |" in report
    assert "## Dimension details" in report
    assert "| case_id | dimension | applicable | score | passed | reason |" in report
    assert (
        "| bad | state | True | 0.0 | False | final state mismatch / 最终状态不匹配 |"
        in report
    )
    assert (
        "| bad | policy | True | 0.0 | False | policy violation / 策略违规 |"
        in report
    )
    assert (
        "| bad | verification | True | 1.0 | True | verified / 已验证 |"
        in report
    )


def test_markdown_report_lists_failed_cases_and_escapes_table_pipes():
    report = render_markdown_report(
        [
            EvalResult(
                "safe|read",
                _dimension(1.0, True, "state | ok"),
                _dimension(1.0, True, "policy | ok"),
                _dimension(1.0, True, "verification | ok"),
            ),
            EvalResult(
                "bad|case",
                _dimension(0.0, False, "state | mismatch"),
                _dimension(0.0, False, "policy | violation"),
                _dimension(0.0, False, "verification | missing"),
            ),
        ]
    )

    assert "| safe\\|read | uncategorized | 1.0 | True | pass / 通过 |" in report
    assert "| safe\\|read | state | True | 1.0 | True | state \\| ok |" in report
    assert "| bad\\|case | state | True | 0.0 | False | state \\| mismatch |" in report
    assert "## Failed cases" in report
    assert (
        "- `bad\\|case`: score=0.0, reason=state \\| mismatch; "
        "policy \\| violation; verification \\| missing" in report
    )


def test_markdown_report_exposes_category_and_tool_policy_failure_reason():
    result = evaluate(
        {
            "id": "missing-verifier",
            "category": "required_tool_missing",
            "expected": {"status": "complete"},
            "actual": {
                "status": "complete",
                "verified": True,
                "tool_calls": ["execute"],
            },
            "tool_policy": {"required_tools": ["execute", "verify_result"]},
        }
    )

    report = render_markdown_report([result])

    assert (
        "| missing-verifier | required_tool_missing | 0.8 | False | "
        "missing required tools: verify_result" in report
    )
    assert (
        "| missing-verifier | policy | True | 0.0 | False | "
        "missing required tools: verify_result" in report
    )


def test_markdown_report_labels_non_applicable_dimension_as_na():
    result = evaluate(
        {
            "id": "clarification",
            "expected": {"status": "NEED_CLARIFICATION"},
            "actual": {"status": "NEED_CLARIFICATION"},
            "required_dimensions": ["state", "policy"],
        }
    )

    report = render_markdown_report([result])

    assert (
        "| clarification | verification | False | N/A | N/A | "
        "not applicable / 不适用 |" in report
    )
