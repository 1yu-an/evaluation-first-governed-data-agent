import argparse
import json
from pathlib import Path
from .evaluator import evaluate
from .reporter import render_markdown_report


def main(path: str, report_path: str | None = None) -> int:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    results = [evaluate(c) for c in cases]
    for r in results:
        print(
            f"{r.case_id}: score={r.overall_score:.1f} "
            f"success={r.success} reason={r.reason}"
        )
    avg = sum(r.overall_score for r in results) / max(1, len(results))
    print(f"Average score / 平均分: {avg:.2f}")
    if report_path:
        report_file = Path(report_path)
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(render_markdown_report(results), encoding="utf-8")
    return 0 if all(r.success for r in results) else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run agent evaluation cases.")
    parser.add_argument("path", nargs="?", default="cases/demo_cases.json")
    parser.add_argument("--report", dest="report_path")
    return parser.parse_args()

if __name__ == '__main__':
    args = _parse_args()
    raise SystemExit(main(args.path, report_path=args.report_path))
