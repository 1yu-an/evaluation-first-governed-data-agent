from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .benchmark import (
    GATE_FAILED_EXIT_CODE,
    BenchmarkSummary,
    evaluate_gate,
    render_gate_result,
    summarize_cases,
)
from .integration_03 import (
    GovernedMySQLRuntime,
    IntegrationExecution,
    load_integration_cases,
    run_integration_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT.parent
DEFAULT_SYSTEM_ROOT = REPOSITORY_ROOT / "03-governed-mysql-data-agent"
DEFAULT_CASES = PROJECT_ROOT / "cases" / "03_integration_cases.json"


def build_integration_report(
    summary: BenchmarkSummary, executions: list[IntegrationExecution]
) -> dict[str, Any]:
    return {
        "actual_source": "dynamic_03_runtime",
        "benchmark_type": "03_integration",
        "cases": [
            {
                "id": execution.result.case_id,
                "raw_result": execution.raw_result,
                "adapted_actual": execution.eval_case["actual"],
                "dimension_result": asdict(execution.result),
            }
            for execution in executions
        ],
        "summary": asdict(summary),
        "system": "03-governed-mysql-data-agent",
    }


def integration_report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_integration_markdown(
    summary: BenchmarkSummary, executions: list[IntegrationExecution]
) -> str:
    averages = summary.dimension_averages
    lines = [
        "# 03 Integration Benchmark",
        "",
        "This is a system benchmark. Every `actual` is produced dynamically by "
        "the real project 03 runtime and then translated by the project 00 adapter.",
        "Case-specific required dimensions distinguish FAIL from N/A; "
        "Verification remains required for normal queries and is N/A for "
        "clarification and standalone policy decisions.",
        "",
        "## Summary",
        "",
        f"- Total cases: {summary.total_cases}",
        f"- Outcome success rate: {_percent(summary.outcome_success_rate)}",
        "- Evaluator conformance rate: "
        f"{_percent(summary.evaluator_conformance_rate)}",
        f"- State average: {averages.state_score:.6f}",
        f"- Policy average: {averages.policy_score:.6f}",
        f"- Verification average: {averages.verification_score:.6f}",
        f"- Overall average: {averages.overall_score:.6f}",
        "",
        "## Category breakdown",
        "",
        "| category | count | outcome success rate | evaluator conformance rate |",
        "|---|---:|---:|---:|",
    ]
    for category, row in summary.category_breakdown.items():
        lines.append(
            f"| {category} | {row.count} | {_percent(row.outcome_success_rate)} | "
            f"{_percent(row.evaluator_conformance_rate)} |"
        )

    failures = [execution for execution in executions if not execution.result.success]
    displayed_failures = failures[:1]
    policy_blocked = next(
        (
            execution
            for execution in failures
            if execution.result.category == "policy_blocked"
        ),
        None,
    )
    if policy_blocked is not None and policy_blocked not in displayed_failures:
        displayed_failures.append(policy_blocked)
    displayed_failures.extend(
        execution
        for execution in failures
        if execution not in displayed_failures
    )
    lines.extend(["", "## Failure evidence", ""])
    if not failures:
        lines.append("No outcome failures were observed.")
    for execution in displayed_failures[:2]:
        responsibility_layers = [
            name
            for name, dimension in (
                ("State", execution.result.state),
                ("Policy", execution.result.policy),
                ("Verification", execution.result.verification),
            )
            if not dimension.passed
        ]
        lines.extend(
            [
                f"### {execution.result.case_id}",
                "",
                "**03 raw output**",
                "",
                "```json",
                json.dumps(execution.raw_result, ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "",
                "**Adapter output**",
                "",
                "```json",
                json.dumps(execution.eval_case["actual"], ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "",
                "**00 dimension result**",
                "",
                "```json",
                json.dumps(asdict(execution.result), ensure_ascii=False, indent=2, sort_keys=True),
                "```",
                "",
                "**Responsibility layer:** " + ", ".join(responsibility_layers),
                "",
            ]
        )
    lines.extend(
        [
            "## Evidence limitation",
            "",
            "Project 03 verifies successful metric queries with a deterministic "
            "non-null metric-key check. This proves that the program emitted and "
            "checked a result signal; it is not production-grade evidence "
            "provenance or independent business-result validation.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write(path: str | Path, content: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the real project 03 system integration benchmark."
    )
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--system-root", default=str(DEFAULT_SYSTEM_ROOT))
    parser.add_argument("--json", dest="json_path", default="reports/03-integration.json")
    parser.add_argument(
        "--markdown", dest="markdown_path", default="reports/03-integration.md"
    )
    parser.add_argument("--gate", dest="gate_path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cases = load_integration_cases(args.cases)
    with tempfile.TemporaryDirectory(prefix="agent-03-integration-") as directory:
        runtime = GovernedMySQLRuntime(
            project_root=args.system_root,
            db_path=Path(directory) / "demo.db",
        )
        runtime.initialize_demo()
        executions = run_integration_cases(cases, runtime)

    eval_cases = [execution.eval_case for execution in executions]
    summary = summarize_cases(eval_cases)
    report = build_integration_report(summary, executions)
    _write(args.json_path, integration_report_to_json(report))
    _write(args.markdown_path, render_integration_markdown(summary, executions))

    averages = summary.dimension_averages
    print(f"03 Integration Benchmark: total_cases={summary.total_cases}")
    print(f"outcome_success_rate={summary.outcome_success_rate:.6f}")
    print(f"evaluator_conformance_rate={summary.evaluator_conformance_rate:.6f}")
    print(f"state_average={averages.state_score:.6f}")
    print(f"policy_average={averages.policy_score:.6f}")
    print(f"verification_average={averages.verification_score:.6f}")
    print(f"overall_average={averages.overall_score:.6f}")
    print(f"JSON report: {args.json_path}")
    print(f"Markdown report: {args.markdown_path}")

    if not args.gate_path:
        return 0
    gate_config = json.loads(Path(args.gate_path).read_text(encoding="utf-8"))
    if not isinstance(gate_config, dict):
        raise ValueError("regression gate config must be a JSON object")
    gate_result = evaluate_gate(summary, gate_config)
    print(render_gate_result(gate_result), end="")
    return 0 if gate_result.passed else GATE_FAILED_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
