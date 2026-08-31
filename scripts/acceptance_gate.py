#!/usr/bin/env python3
"""Cross-platform repository acceptance gate.

This module orchestrates the repository's existing validators, tests, and
fixed benchmark instead of reimplementing them.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import Callable, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PASS = "PASS"
FAIL = "FAIL"
MISSING_TOOL = "MISSING_TOOL"


@dataclass(frozen=True)
class Check:
    """One required acceptance check."""

    name: str
    command: tuple[str, ...]
    cwd: Path = ROOT
    required_tools: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CheckResult:
    """The terminal status of one acceptance check."""

    name: str
    status: str
    detail: str = ""


CommandRunner = Callable[[Check], int]
ToolFinder = Callable[[str], str | None]


def build_checks(with_mysql: bool = False, root: Path = ROOT) -> list[Check]:
    """Build the single source of truth for repository acceptance commands."""

    python = sys.executable
    # Resolve mvn.cmd on Windows because shell=False does not consistently
    # apply PATHEXT lookup for batch files.
    maven = shutil.which("mvn") or "mvn"

    checks = [
        Check("Repository validation", (python, "scripts/validate_all.py"), root),
        Check(
            "Repository audit tests",
            (python, "-m", "pytest", "-q", "tests/test_audit_repo.py"),
            root,
        ),
        Check("Repository audit", (python, "scripts/audit_repo.py"), root),
        Check(
            "Acceptance gate tests",
            (python, "-m", "pytest", "-q", "tests/test_acceptance_gate.py"),
            root,
        ),
        Check("00 Python tests", (python, "-m", "pytest", "-q"), root / "00-agent-eval-harness"),
        Check("02 Python tests", (python, "-m", "pytest", "-q"), root / "02-verified-browser-ops-agent"),
        Check("03 Python tests", (python, "-m", "pytest", "-q"), root / "03-governed-mysql-data-agent"),
        Check("04 Python tests", (python, "-m", "pytest", "-q"), root / "04-java-migration-agent"),
        Check("05 Python tests", (python, "-m", "pytest", "-q"), root / "05-evidence-deep-research-agent"),
        Check(
            "01 Java tests",
            (maven, "test"),
            root / "01-agent-control-plane",
            required_tools=("java", "mvn"),
        ),
        Check(
            "06 Java tests",
            (maven, "test"),
            root / "06-a2a-spring-boot-starter",
            required_tools=("java", "mvn"),
        ),
        Check(
            "03 Benchmark Gate",
            (
                python,
                "-m",
                "src.integration_benchmark",
                "--gate",
                "config/03_regression_gate.json",
            ),
            root / "00-agent-eval-harness",
        ),
        Check(
            "03 V3 Analytics Gate",
            (
                python,
                "-m",
                "src.v3_analytics_benchmark",
                "--gate",
            ),
            root / "00-agent-eval-harness",
        ),
    ]
    if with_mysql:
        checks.append(
            Check(
                "03 MySQL integration",
                (python, "-m", "pytest", "-q", "tests/test_mysql_integration.py"),
                root / "03-governed-mysql-data-agent",
                env={"RUN_MYSQL_INTEGRATION": "1"},
            )
        )
    return checks


def _display_command(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def run_subprocess(check: Check) -> int:
    """Run one command without a shell and return its exit code."""

    environment = os.environ.copy()
    environment.update(check.env)
    completed = subprocess.run(
        check.command,
        cwd=check.cwd,
        env=environment,
        check=False,
    )
    return completed.returncode


def execute_checks(
    checks: Iterable[Check],
    command_runner: CommandRunner = run_subprocess,
    tool_finder: ToolFinder = shutil.which,
) -> list[CheckResult]:
    """Execute every check and fail closed on every non-success condition."""

    results: list[CheckResult] = []
    for check in checks:
        print(f"\n== {check.name} ==", flush=True)
        missing = [tool for tool in check.required_tools if tool_finder(tool) is None]
        if missing:
            detail = f"missing required tool(s): {', '.join(missing)}"
            print(f"{MISSING_TOOL}: {detail}", flush=True)
            results.append(CheckResult(check.name, MISSING_TOOL, detail))
            continue

        print(f"$ {_display_command(check.command)}", flush=True)
        try:
            return_code = command_runner(check)
        except OSError as exc:
            detail = f"command could not start: {exc}"
            print(f"{FAIL}: {detail}", flush=True)
            results.append(CheckResult(check.name, FAIL, detail))
            continue
        except Exception as exc:  # defensive fail-closed boundary
            detail = f"unexpected runner error: {exc}"
            print(f"{FAIL}: {detail}", flush=True)
            results.append(CheckResult(check.name, FAIL, detail))
            continue

        if return_code == 0:
            results.append(CheckResult(check.name, PASS))
        else:
            detail = f"exit code {return_code}"
            print(f"{FAIL}: {detail}", flush=True)
            results.append(CheckResult(check.name, FAIL, detail))
    return results


def print_summary(results: Sequence[CheckResult]) -> None:
    """Print stable, human- and CI-readable terminal statuses."""

    print("\nRepository Acceptance Gate\n")
    width = max((len(result.name) for result in results), default=0)
    for result in results:
        suffix = f" ({result.detail})" if result.detail else ""
        print(f"{result.name:<{width}}  {result.status}{suffix}")
    final_status = PASS if results and all(result.status == PASS for result in results) else FAIL
    print(f"\nFINAL RESULT: {final_status}")


def run_acceptance(
    checks: Iterable[Check],
    command_runner: CommandRunner = run_subprocess,
    tool_finder: ToolFinder = shutil.which,
) -> int:
    results = execute_checks(checks, command_runner, tool_finder)
    print_summary(results)
    return 0 if results and all(result.status == PASS for result in results) else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the repository acceptance gate")
    parser.add_argument(
        "--with-mysql",
        action="store_true",
        help="also run the external, opt-in MySQL 8.0 integration suite",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return run_acceptance(build_checks(with_mysql=args.with_mysql))


if __name__ == "__main__":
    raise SystemExit(main())
