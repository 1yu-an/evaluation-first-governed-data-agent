import json
from pathlib import Path

import pytest

from src import benchmark


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _case(case_id, category, expected_success, expected, actual, metrics=None):
    case = {
        "id": case_id,
        "category": category,
        "expected_success": expected_success,
        "expected": expected,
        "actual": actual,
    }
    if metrics is not None:
        case["metrics"] = metrics
    return case


@pytest.fixture
def conforming_corpus():
    return [
        _case(
            "success",
            "normal",
            True,
            {"status": "complete"},
            {"status": "complete", "verified": True},
        ),
        _case(
            "state-failure",
            "adversarial",
            False,
            {"status": "complete"},
            {"status": "pending", "verified": True},
        ),
        _case(
            "policy-failure",
            "adversarial",
            False,
            {"status": "complete"},
            {
                "status": "complete",
                "verified": True,
                "policy_violation": True,
            },
        ),
        _case(
            "verification-failure",
            "adversarial",
            False,
            {"status": "complete"},
            {"status": "complete", "verified": False},
        ),
    ]


def test_intentional_failures_have_low_outcome_and_full_conformance(
    conforming_corpus,
):
    summary = benchmark.summarize_cases(conforming_corpus)

    assert summary.total_cases == 4
    assert summary.outcome_success_rate == 0.25
    assert summary.evaluator_conformance_rate == 1.0
    assert summary.failure_analysis.conformance_mismatches == []


def test_wrong_verdict_reduces_evaluator_conformance(conforming_corpus):
    corpus = [dict(case) for case in conforming_corpus]
    corpus[0]["expected_success"] = False

    summary = benchmark.summarize_cases(corpus)

    assert summary.outcome_success_rate == 0.25
    assert summary.evaluator_conformance_rate == 0.75
    assert summary.failure_analysis.conformance_mismatches == ["success"]


def test_category_breakdown_and_dimension_averages_are_correct(
    conforming_corpus,
):
    summary = benchmark.summarize_cases(conforming_corpus)

    assert list(summary.category_breakdown) == ["adversarial", "normal"]
    assert summary.category_breakdown["normal"].count == 1
    assert summary.category_breakdown["normal"].outcome_success_rate == 1.0
    adversarial = summary.category_breakdown["adversarial"]
    assert adversarial.count == 3
    assert adversarial.outcome_success_rate == 0.0
    assert adversarial.evaluator_conformance_rate == 1.0
    assert summary.dimension_averages.state_score == 0.75
    assert summary.dimension_averages.policy_score == 0.75
    assert summary.dimension_averages.verification_score == 0.75
    assert summary.dimension_averages.overall_score == pytest.approx(0.75)


def test_full_33_case_fixture_corpus_conforms():
    cases = json.loads(
        (PROJECT_ROOT / "cases" / "eval_cases.json").read_text(encoding="utf-8")
    )

    summary = benchmark.summarize_cases(cases)

    assert summary.total_cases == 33
    assert summary.outcome_success_rate == pytest.approx(8 / 33)
    assert summary.evaluator_conformance_rate == 1.0
    assert summary.dimension_averages.state_score == pytest.approx(26 / 33)
    assert summary.dimension_averages.policy_score == pytest.approx(18 / 33)
    assert summary.dimension_averages.verification_score == pytest.approx(27 / 33)
    assert summary.dimension_averages.overall_score == pytest.approx(24.6 / 33)
    assert summary.failure_analysis.failing_dimension_counts == {
        "state": 7,
        "policy": 15,
        "verification": 6,
    }
    assert all(
        category.evaluator_conformance_rate == 1.0
        for category in summary.category_breakdown.values()
    )


def test_json_and_markdown_reports_share_key_metrics(conforming_corpus):
    summary = benchmark.summarize_cases(conforming_corpus)

    json_report = benchmark.summary_to_json(summary)
    markdown_report = benchmark.render_benchmark_markdown(summary)
    parsed = json.loads(json_report)

    assert json_report == benchmark.summary_to_json(summary)
    assert parsed["total_cases"] == 4
    assert parsed["outcome_success_rate"] == 0.25
    assert parsed["evaluator_conformance_rate"] == 1.0
    assert "- Total cases: 4" in markdown_report
    assert "- Outcome success rate: 25.00%" in markdown_report
    assert "- Evaluator conformance rate: 100.00%" in markdown_report
    assert "| State | 0.750000 |" in markdown_report


def test_missing_metrics_are_reported_as_unavailable(conforming_corpus):
    summary = benchmark.summarize_cases(conforming_corpus)
    report = benchmark.render_benchmark_markdown(summary)

    assert summary.metrics.latency_available is False
    assert summary.metrics.average_latency_ms is None
    assert summary.metrics.cost_available is False
    assert summary.metrics.total_cost is None
    assert "- Latency: not available" in report
    assert "- Cost: not available" in report


def test_optional_metrics_are_aggregated_when_present():
    cases = [
        _case(
            "one",
            "metrics",
            True,
            {},
            {"verified": True},
            metrics={"latency_ms": 100, "cost": 0.1},
        ),
        _case(
            "two",
            "metrics",
            True,
            {},
            {"verified": True},
            metrics={"latency_ms": 200, "cost": 0.3},
        ),
    ]

    metrics = benchmark.summarize_cases(cases).metrics

    assert metrics.latency_case_count == 2
    assert metrics.average_latency_ms == 150.0
    assert metrics.cost_case_count == 2
    assert metrics.total_cost == pytest.approx(0.4)
    assert metrics.average_cost == pytest.approx(0.2)


def test_gate_passes_at_threshold_and_fails_below_threshold(conforming_corpus):
    passing_summary = benchmark.summarize_cases(conforming_corpus)
    passing = benchmark.evaluate_gate(
        passing_summary, {"min_evaluator_conformance_rate": 1.0}
    )
    assert passing.passed is True
    assert benchmark.render_gate_result(passing) == "REGRESSION GATE PASS\n"

    regressed_corpus = [dict(case) for case in conforming_corpus]
    regressed_corpus[0]["expected_success"] = False
    regressed_summary = benchmark.summarize_cases(regressed_corpus)
    failed = benchmark.evaluate_gate(
        regressed_summary, {"min_evaluator_conformance_rate": 1.0}
    )

    assert failed.passed is False
    assert failed.failures[0].metric == "evaluator_conformance_rate"
    assert failed.failures[0].actual == 0.75
    assert failed.failures[0].threshold == 1.0
    rendered = benchmark.render_gate_result(failed)
    assert "metric=evaluator_conformance_rate" in rendered
    assert "actual=0.750000" in rendered
    assert "threshold=1.000000" in rendered


def test_benchmark_cli_ignores_outcome_failures_but_enforces_gate(
    tmp_path, conforming_corpus, capsys
):
    corpus_path = tmp_path / "corpus.json"
    json_path = tmp_path / "benchmark.json"
    markdown_path = tmp_path / "benchmark.md"
    gate_path = tmp_path / "gate.json"
    corpus_path.write_text(json.dumps(conforming_corpus), encoding="utf-8")
    gate_path.write_text(
        json.dumps({"min_evaluator_conformance_rate": 1.0}), encoding="utf-8"
    )

    assert (
        benchmark.main(
            [
                str(corpus_path),
                "--json",
                str(json_path),
                "--markdown",
                str(markdown_path),
            ]
        )
        == 0
    )
    assert json_path.exists()
    assert markdown_path.exists()

    assert (
        benchmark.main(
            [
                str(corpus_path),
                "--json",
                str(json_path),
                "--markdown",
                str(markdown_path),
                "--gate",
                str(gate_path),
            ]
        )
        == 0
    )

    regressed = [dict(case) for case in conforming_corpus]
    regressed[0]["expected_success"] = False
    corpus_path.write_text(json.dumps(regressed), encoding="utf-8")
    assert (
        benchmark.main(
            [
                str(corpus_path),
                "--json",
                str(json_path),
                "--markdown",
                str(markdown_path),
                "--gate",
                str(gate_path),
            ]
        )
        == benchmark.GATE_FAILED_EXIT_CODE
    )
    output = capsys.readouterr().out
    assert "REGRESSION GATE FAIL" in output
    assert "metric=evaluator_conformance_rate" in output
    assert "actual=0.750000" in output
    assert "threshold=1.000000" in output


@pytest.mark.parametrize(
    "case",
    [
        {"id": "missing", "expected": {}, "actual": {"verified": True}},
        {
            "id": "invalid",
            "expected_success": "yes",
            "expected": {},
            "actual": {"verified": True},
        },
    ],
)
def test_benchmark_requires_boolean_expected_success(case):
    with pytest.raises(ValueError, match="expected_success"):
        benchmark.summarize_cases([case])
