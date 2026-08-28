from src.evaluator import EvalResult
from src.reporter import render_markdown_report


def test_markdown_report_contains_summary_and_cases_table():
    report = render_markdown_report(
        [
            EvalResult("ok", True, 1.0, "pass / 通过"),
            EvalResult("bad", False, 0.2, "not verified / 未验证"),
        ],
        title="Demo Report",
    )

    assert "# Demo Report" in report
    assert "- Total cases: 2" in report
    assert "- Passed: 1" in report
    assert "- Failed: 1" in report
    assert "- Average score: 0.60" in report
    assert "| case_id | score | success | reason |" in report
    assert "| ok | 1.0 | True | pass / 通过 |" in report


def test_markdown_report_lists_failed_cases_and_escapes_table_pipes():
    report = render_markdown_report(
        [
            EvalResult("safe|read", True, 1.0, "pass | ok"),
            EvalResult("bad|case", False, 0.0, "state | mismatch"),
        ]
    )

    assert "| safe\\|read | 1.0 | True | pass \\| ok |" in report
    assert "| bad\\|case | 0.0 | False | state \\| mismatch |" in report
    assert "## Failed cases" in report
    assert "- `bad\\|case`: score=0.0, reason=state \\| mismatch" in report
