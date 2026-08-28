from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .evaluator import EvalResult, evaluate


BENCHMARK_SCHEMA_VERSION = "1.0"
GATE_FAILED_EXIT_CODE = 3


@dataclass(frozen=True)
class DimensionAverages:
    state_score: float
    policy_score: float
    verification_score: float
    overall_score: float


@dataclass(frozen=True)
class CategorySummary:
    count: int
    outcome_success_rate: float
    evaluator_conformance_rate: float


@dataclass(frozen=True)
class CountItem:
    name: str
    count: int


@dataclass(frozen=True)
class FailureAnalysis:
    failing_dimension_counts: dict[str, int]
    top_outcome_failure_categories: list[CountItem]
    top_failure_reasons: list[CountItem]
    conformance_mismatches: list[str]


@dataclass(frozen=True)
class MetricsSummary:
    latency_available: bool
    latency_case_count: int
    average_latency_ms: float | None
    cost_available: bool
    cost_case_count: int
    total_cost: float | None
    average_cost: float | None


@dataclass(frozen=True)
class BenchmarkSummary:
    schema_version: str
    total_cases: int
    outcome_success_rate: float
    evaluator_conformance_rate: float
    dimension_averages: DimensionAverages
    category_breakdown: dict[str, CategorySummary]
    failure_analysis: FailureAnalysis
    metrics: MetricsSummary


@dataclass(frozen=True)
class GateFailure:
    metric: str
    actual: float
    threshold: float


@dataclass(frozen=True)
class GateResult:
    passed: bool
    failures: tuple[GateFailure, ...]


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _average(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _expected_success(case: Mapping[str, Any]) -> bool:
    if "expected_success" not in case:
        raise ValueError("benchmark case missing required field: expected_success")
    value = case["expected_success"]
    if not isinstance(value, bool):
        raise ValueError("expected_success must be a boolean")
    return value


def _numeric_metric(
    metrics: Mapping[str, Any], metric_name: str, case_id: str
) -> float | None:
    if metric_name not in metrics:
        return None
    value = metrics[metric_name]
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(
            f"metrics.{metric_name} for case {case_id} must be a non-negative number"
        )
    return float(value)


def _metrics_summary(cases: Sequence[Mapping[str, Any]]) -> MetricsSummary:
    latencies = []
    costs = []
    for case in cases:
        if "metrics" not in case:
            continue
        metrics = case["metrics"]
        if not isinstance(metrics, Mapping):
            raise ValueError(f"metrics for case {case.get('id')} must be an object")
        latency = _numeric_metric(metrics, "latency_ms", str(case.get("id")))
        cost = _numeric_metric(metrics, "cost", str(case.get("id")))
        if latency is not None:
            latencies.append(latency)
        if cost is not None:
            costs.append(cost)

    return MetricsSummary(
        latency_available=bool(latencies),
        latency_case_count=len(latencies),
        average_latency_ms=_average(latencies) if latencies else None,
        cost_available=bool(costs),
        cost_case_count=len(costs),
        total_cost=sum(costs) if costs else None,
        average_cost=_average(costs) if costs else None,
    )


def _top_counts(counter: Counter[str], limit: int) -> list[CountItem]:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [CountItem(name=name, count=count) for name, count in ordered[:limit]]


def summarize_cases(
    cases: Sequence[Mapping[str, Any]], top_n: int = 5
) -> BenchmarkSummary:
    if not cases:
        raise ValueError("benchmark requires at least one case")

    evaluated: list[tuple[Mapping[str, Any], bool, EvalResult]] = []
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("benchmark cases must be objects")
        expected_success = _expected_success(case)
        evaluated.append((case, expected_success, evaluate(case)))

    total = len(evaluated)
    outcome_successes = sum(result.success for _, _, result in evaluated)
    conforming = sum(
        result.success == expected_success
        for _, expected_success, result in evaluated
    )

    category_rows: dict[str, list[tuple[bool, EvalResult]]] = defaultdict(list)
    failing_dimensions: Counter[str] = Counter()
    failure_categories: Counter[str] = Counter()
    failure_reasons: Counter[str] = Counter()
    conformance_mismatches = []

    for _, expected_success, result in evaluated:
        category_rows[result.category].append((expected_success, result))
        if result.success != expected_success:
            conformance_mismatches.append(result.case_id)
        if result.success:
            continue
        failure_categories[result.category] += 1
        for dimension_name, dimension in (
            ("state", result.state),
            ("policy", result.policy),
            ("verification", result.verification),
        ):
            if dimension.applicable and not dimension.passed:
                failing_dimensions[dimension_name] += 1
                failure_reasons[dimension.reason] += 1

    category_breakdown = {}
    for category in sorted(category_rows):
        rows = category_rows[category]
        category_breakdown[category] = CategorySummary(
            count=len(rows),
            outcome_success_rate=_rate(
                sum(result.success for _, result in rows), len(rows)
            ),
            evaluator_conformance_rate=_rate(
                sum(result.success == expected for expected, result in rows),
                len(rows),
            ),
        )

    results = [result for _, _, result in evaluated]
    state_scores = [result.state.score for result in results if result.state.applicable]
    policy_scores = [
        result.policy.score for result in results if result.policy.applicable
    ]
    verification_scores = [
        result.verification.score
        for result in results
        if result.verification.applicable
    ]
    return BenchmarkSummary(
        schema_version=BENCHMARK_SCHEMA_VERSION,
        total_cases=total,
        outcome_success_rate=_rate(outcome_successes, total),
        evaluator_conformance_rate=_rate(conforming, total),
        dimension_averages=DimensionAverages(
            state_score=_average(state_scores),
            policy_score=_average(policy_scores),
            verification_score=_average(verification_scores),
            overall_score=_average([result.overall_score for result in results]),
        ),
        category_breakdown=category_breakdown,
        failure_analysis=FailureAnalysis(
            failing_dimension_counts={
                name: failing_dimensions.get(name, 0)
                for name in ("state", "policy", "verification")
            },
            top_outcome_failure_categories=_top_counts(failure_categories, top_n),
            top_failure_reasons=_top_counts(failure_reasons, top_n),
            conformance_mismatches=sorted(conformance_mismatches),
        ),
        metrics=_metrics_summary([case for case, _, _ in evaluated]),
    )


def summary_to_json(summary: BenchmarkSummary) -> str:
    return json.dumps(
        asdict(summary), ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_benchmark_markdown(summary: BenchmarkSummary) -> str:
    lines = [
        "# Benchmark Summary",
        "",
        "This corpus is a harness validation fixture set, not a production Agent "
        "benchmark. Evaluator conformance is the primary regression signal; "
        "outcome success describes the supplied adversarial executions.",
        "",
        "## Summary",
        "",
        f"- Total cases: {summary.total_cases}",
        f"- Outcome success rate: {_percent(summary.outcome_success_rate)}",
        "- Evaluator conformance rate: "
        f"{_percent(summary.evaluator_conformance_rate)}",
        "",
        "## Dimension averages",
        "",
        "| dimension | average score |",
        "|---|---:|",
        f"| State | {summary.dimension_averages.state_score:.6f} |",
        f"| Policy | {summary.dimension_averages.policy_score:.6f} |",
        "| Verification | "
        f"{summary.dimension_averages.verification_score:.6f} |",
        f"| Overall | {summary.dimension_averages.overall_score:.6f} |",
        "",
        "## Category breakdown",
        "",
        "| category | count | outcome success rate | evaluator conformance rate |",
        "|---|---:|---:|---:|",
    ]

    for category, category_summary in summary.category_breakdown.items():
        lines.append(
            f"| {category} | {category_summary.count} | "
            f"{_percent(category_summary.outcome_success_rate)} | "
            f"{_percent(category_summary.evaluator_conformance_rate)} |"
        )

    counts = summary.failure_analysis.failing_dimension_counts
    lines.extend(
        [
            "",
            "## Failure analysis",
            "",
            f"- State failures: {counts['state']}",
            f"- Policy failures: {counts['policy']}",
            f"- Verification failures: {counts['verification']}",
            "",
            "### Top outcome failure categories",
            "",
        ]
    )
    if summary.failure_analysis.top_outcome_failure_categories:
        lines.extend(
            f"- {item.name}: {item.count}"
            for item in summary.failure_analysis.top_outcome_failure_categories
        )
    else:
        lines.append("None")

    lines.extend(["", "### Top failure reasons", ""])
    if summary.failure_analysis.top_failure_reasons:
        lines.extend(
            f"- {item.name}: {item.count}"
            for item in summary.failure_analysis.top_failure_reasons
        )
    else:
        lines.append("None")

    lines.extend(["", "### Evaluator conformance mismatches", ""])
    if summary.failure_analysis.conformance_mismatches:
        lines.extend(
            f"- {case_id}"
            for case_id in summary.failure_analysis.conformance_mismatches
        )
    else:
        lines.append("None")

    lines.extend(["", "## Metrics", ""])
    if summary.metrics.latency_available:
        lines.append(
            f"- Latency: {summary.metrics.latency_case_count} cases, "
            f"average={summary.metrics.average_latency_ms:.6f} ms"
        )
    else:
        lines.append("- Latency: not available")
    if summary.metrics.cost_available:
        lines.append(
            f"- Cost: {summary.metrics.cost_case_count} cases, "
            f"total={summary.metrics.total_cost:.6f}, "
            f"average={summary.metrics.average_cost:.6f}"
        )
    else:
        lines.append("- Cost: not available")

    return "\n".join(lines) + "\n"


def _dimension_metric(
    summary: BenchmarkSummary, attribute: str
) -> float:
    return float(getattr(summary.dimension_averages, attribute))


GATE_METRICS: dict[str, tuple[str, Callable[[BenchmarkSummary], float]]] = {
    "min_evaluator_conformance_rate": (
        "evaluator_conformance_rate",
        lambda summary: summary.evaluator_conformance_rate,
    ),
    "min_outcome_success_rate": (
        "outcome_success_rate",
        lambda summary: summary.outcome_success_rate,
    ),
    "min_state_score": (
        "state_score",
        lambda summary: _dimension_metric(summary, "state_score"),
    ),
    "min_policy_score": (
        "policy_score",
        lambda summary: _dimension_metric(summary, "policy_score"),
    ),
    "min_verification_score": (
        "verification_score",
        lambda summary: _dimension_metric(summary, "verification_score"),
    ),
    "min_overall_score": (
        "overall_score",
        lambda summary: _dimension_metric(summary, "overall_score"),
    ),
}


def evaluate_gate(
    summary: BenchmarkSummary, config: Mapping[str, Any]
) -> GateResult:
    unknown = sorted(set(config) - set(GATE_METRICS))
    if unknown:
        raise ValueError("unknown regression gate metrics: " + ", ".join(unknown))

    failures = []
    for config_key in sorted(config):
        threshold = config[config_key]
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold)
            or not 0.0 <= threshold <= 1.0
        ):
            raise ValueError(f"{config_key} must be a number between 0 and 1")
        metric_name, getter = GATE_METRICS[config_key]
        actual = getter(summary)
        if actual < float(threshold):
            failures.append(
                GateFailure(
                    metric=metric_name,
                    actual=actual,
                    threshold=float(threshold),
                )
            )

    return GateResult(passed=not failures, failures=tuple(failures))


def render_gate_result(result: GateResult) -> str:
    if result.passed:
        return "REGRESSION GATE PASS\n"
    lines = ["REGRESSION GATE FAIL"]
    lines.extend(
        f"metric={failure.metric} actual={failure.actual:.6f} "
        f"threshold={failure.threshold:.6f}"
        for failure in result.failures
    )
    return "\n".join(lines) + "\n"


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_report(path: str, content: str) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate benchmark reports and optionally apply a regression gate."
    )
    parser.add_argument("path", help="JSON fixture corpus with expected_success")
    parser.add_argument("--json", dest="json_path", default="reports/benchmark.json")
    parser.add_argument(
        "--markdown", dest="markdown_path", default="reports/benchmark.md"
    )
    parser.add_argument("--gate", dest="gate_path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cases = _load_json(args.path)
    if not isinstance(cases, list):
        raise ValueError("benchmark corpus must be a JSON array")

    summary = summarize_cases(cases)
    _write_report(args.json_path, summary_to_json(summary))
    _write_report(args.markdown_path, render_benchmark_markdown(summary))
    print(
        f"Benchmark complete: total_cases={summary.total_cases} "
        f"outcome_success_rate={summary.outcome_success_rate:.6f} "
        "evaluator_conformance_rate="
        f"{summary.evaluator_conformance_rate:.6f}"
    )
    print(f"JSON report: {args.json_path}")
    print(f"Markdown report: {args.markdown_path}")

    if not args.gate_path:
        return 0
    gate_config = _load_json(args.gate_path)
    if not isinstance(gate_config, Mapping):
        raise ValueError("regression gate config must be a JSON object")
    gate_result = evaluate_gate(summary, gate_config)
    print(render_gate_result(gate_result), end="")
    return 0 if gate_result.passed else GATE_FAILED_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
