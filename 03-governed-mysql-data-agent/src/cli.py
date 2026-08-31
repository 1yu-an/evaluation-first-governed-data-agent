"""CLI for asking, explaining, and validating personal Domain Profiles."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .agent import DataAgent
from .executor import (
    ExecutionError,
    MySQLExecutor,
    _load_mysql_connector,
    executor_from_env,
)
from .profile import (
    ProfileValidationError,
    load_default_profile,
    load_profile,
    required_schema,
)
from .schema_validation import (
    SchemaInspectionError,
    SchemaValidationError,
    validate_mysql_config_schema,
)


COMMANDS = {"ask", "explain", "validate-profile"}


def _selected_profile(path: str | None):
    configured = path or os.environ.get("DATA_AGENT_PROFILE", "").strip()
    return load_profile(Path(configured)) if configured else load_default_profile()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("ask", "explain"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--profile")
        if command == "ask":
            subparser.add_argument("--db-path", default="demo.db")
        subparser.add_argument("question", nargs="+")
    validate = subparsers.add_parser("validate-profile")
    validate.add_argument("--profile", required=True)
    validate.add_argument("--check-mysql-schema", action="store_true")
    return parser


def _preflight_mysql(profile, executor) -> None:
    if isinstance(executor, MySQLExecutor):
        connector = executor._connector_module or _load_mysql_connector()
        validate_mysql_config_schema(profile, executor.config, connector)


def _concise_answer(result: dict) -> dict:
    if result.get("status") != "OK":
        return {
            "status": result.get("status", "ERROR"),
            "reason": result.get("reason", "unknown failure"),
            "evidence": {},
        }
    return {
        "status": "success",
        "profile_id": result["profile_id"],
        "metric": result["metric"],
        "filters": result["filters"],
        "value": result["value"],
        "verified": result["verified"],
        "evidence": {
            "row_count": 1,
            "result_key": result["metric"],
        },
    }


def _new_cli(argv: list[str]) -> tuple[dict, int]:
    arguments = _parser().parse_args(argv)
    profile = _selected_profile(arguments.profile)
    if arguments.command == "validate-profile":
        if arguments.check_mysql_schema:
            executor = executor_from_env()
            if not isinstance(executor, MySQLExecutor):
                raise ExecutionError(
                    "--check-mysql-schema requires DATA_AGENT_EXECUTOR=mysql"
                )
            _preflight_mysql(profile, executor)
        return {
            "status": "valid",
            "profile_id": profile.profile_id,
            "required_schema": {
                table: sorted(columns)
                for table, columns in required_schema(profile).items()
            },
            "mysql_schema_checked": arguments.check_mysql_schema,
        }, 0

    question = " ".join(arguments.question)
    if arguments.command == "explain":
        result = DataAgent(profile=profile).explain(question)
        return result, 0 if result["status"] == "OK" else 1
    executor = executor_from_env(arguments.db_path)
    _preflight_mysql(profile, executor)
    result = DataAgent(executor=executor, profile=profile).answer(question)
    concise = _concise_answer(result)
    return concise, 0 if concise["status"] == "success" else 1


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    try:
        if values and values[0] in COMMANDS:
            result, exit_code = _new_cli(values)
        else:
            question = " ".join(values) or "revenue"
            executor = executor_from_env()
            profile = _selected_profile(None)
            _preflight_mysql(profile, executor)
            result = DataAgent(executor=executor, profile=profile).answer(question)
            exit_code = 0 if result["status"] != "ERROR" else 2
    except (
        ExecutionError,
        ProfileValidationError,
        SchemaInspectionError,
        SchemaValidationError,
    ) as error:
        result = {"status": "ERROR", "reason": str(error), "evidence": {}}
        exit_code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
