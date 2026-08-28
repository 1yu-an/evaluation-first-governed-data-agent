from typing import Iterable, List

from .evaluator import EvalResult


def _escape_markdown_table_cell(value: object) -> str:
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def render_markdown_report(results: Iterable[EvalResult], title: str = "Agent Eval Report") -> str:
    """Render evaluation results as a Markdown benchmark report."""
    result_list: List[EvalResult] = list(results)
    total = len(result_list)
    passed = sum(1 for result in result_list if result.success)
    failed = total - passed
    average = sum(result.overall_score for result in result_list) / max(1, total)
    failed_results = [result for result in result_list if not result.success]

    lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        f"- Total cases: {total}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        f"- Average score: {average:.2f}",
        "",
        "## Cases",
        "",
        "| case_id | category | score | success | reason |",
        "|---|---|---:|:---:|---|",
    ]

    for result in result_list:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_markdown_table_cell(result.case_id),
                    _escape_markdown_table_cell(result.category),
                    f"{result.overall_score:.1f}",
                    str(result.success),
                    _escape_markdown_table_cell(result.reason),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Dimension details",
            "",
            "| case_id | dimension | applicable | score | passed | reason |",
            "|---|---|:---:|---:|:---:|---|",
        ]
    )

    for result in result_list:
        for dimension_name, dimension in (
            ("state", result.state),
            ("policy", result.policy),
            ("verification", result.verification),
        ):
            score = f"{dimension.score:.1f}" if dimension.applicable else "N/A"
            passed = str(dimension.passed) if dimension.applicable else "N/A"
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_markdown_table_cell(result.case_id),
                        dimension_name,
                        str(dimension.applicable),
                        score,
                        passed,
                        _escape_markdown_table_cell(dimension.reason),
                    ]
                )
                + " |"
            )

    lines.extend(["", "## Failed cases", ""])

    if failed_results:
        for result in failed_results:
            lines.append(
                f"- `{_escape_markdown_table_cell(result.case_id)}`: "
                f"score={result.overall_score:.1f}, "
                f"reason={_escape_markdown_table_cell(result.reason)}"
            )
    else:
        lines.append("None")

    return "\n".join(lines) + "\n"
