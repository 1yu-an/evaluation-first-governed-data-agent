import json

import pytest

import src.runner as runner
from src.runner import main


@pytest.fixture
def fake_report_renderer():
    calls = []

    def render(results):
        result_list = list(results)
        calls.append(result_list)
        return "fake report from patched renderer\n"

    render.calls = calls
    return render


def test_runner_returns_zero_when_all_cases_pass(tmp_path):
    cases_path = tmp_path / "passing_cases.json"
    report_path = tmp_path / "nested" / "reports" / "passing.md"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "pass",
                    "expected": {"action": "read"},
                    "actual": {"action": "read", "verified": True},
                }
            ]
        ),
        encoding="utf-8",
    )

    assert main(str(cases_path), report_path=str(report_path)) == 0
    report = report_path.read_text(encoding="utf-8")
    assert report_path.exists()
    assert "- Total cases: 1" in report
    assert "- Passed: 1" in report
    assert "- Failed: 0" in report
    assert "| pass | 1.0 | True | pass / 通过 |" in report


def test_runner_returns_two_when_any_case_fails(tmp_path):
    cases_path = tmp_path / "failing_cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "fail",
                    "expected": {"plan": "PRO"},
                    "actual": {"plan": "BASIC", "verified": False},
                }
            ]
        ),
        encoding="utf-8",
    )

    assert main(str(cases_path)) == 2


def test_runner_uses_its_report_renderer_lookup(
    tmp_path, monkeypatch, fake_report_renderer
):
    cases_path = tmp_path / "cases.json"
    report_path = tmp_path / "report.md"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "patched-renderer-case",
                    "expected": {"action": "read"},
                    "actual": {"action": "read", "verified": True},
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "render_markdown_report", fake_report_renderer)

    assert runner.main(str(cases_path), report_path=str(report_path)) == 0
    assert report_path.read_text(encoding="utf-8") == (
        "fake report from patched renderer\n"
    )
    assert len(fake_report_renderer.calls) == 1
    received_results = fake_report_renderer.calls[0]
    assert len(received_results) == 1
    assert received_results[0].case_id == "patched-renderer-case"
    assert received_results[0].score == 1.0
    assert received_results[0].success is True
