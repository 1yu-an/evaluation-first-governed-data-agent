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
    ProfileScaffoldError,
    ProfileValidationError,
    load_default_profile,
    load_profile,
    required_schema,
    write_profile_scaffold,
)
from .schema_validation import (
    SchemaInspectionError,
    SchemaValidationError,
    validate_mysql_config_schema,
)


COMMANDS = {"ask", "explain", "init-profile", "validate-profile"}


def _selected_profile(path: str | None):
    configured = path or os.environ.get("DATA_AGENT_PROFILE", "").strip()
    return load_profile(Path(configured)) if configured else load_default_profile()


def _selected_db_path(path: str | None) -> str:
    return path or os.environ.get("DATA_AGENT_DB_PATH", "").strip() or "demo.db"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description=(
            "Run governed personal metrics. CLI values override DATA_AGENT_* "
            "environment defaults."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("ask", "explain"):
        subparser = subparsers.add_parser(
            command,
            help=(
                "execute and verify one question"
                if command == "ask"
                else "resolve and compile without database execution"
            ),
        )
        subparser.add_argument(
            "--profile",
            help="JSON Profile path (overrides DATA_AGENT_PROFILE)",
        )
        if command == "ask":
            subparser.add_argument(
                "--db-path",
                help=(
                    "SQLite path (overrides DATA_AGENT_DB_PATH; default demo.db)"
                ),
            )
        subparser.add_argument("question", nargs="+", help="business question")
    validate = subparsers.add_parser(
        "validate-profile",
        help="validate Profile offline or against configured MySQL metadata",
    )
    validate.add_argument(
        "--profile",
        help="JSON Profile path (overrides DATA_AGENT_PROFILE; default demo)",
    )
    validate.add_argument(
        "--check-mysql-schema",
        action="store_true",
        help="also compare required tables/columns with configured MySQL",
    )
    initialize = subparsers.add_parser(
        "init-profile",
        help="create a legal minimal JSON Profile without database access",
    )
    initialize.add_argument("path", help="new JSON Profile path")
    initialize.add_argument(
        "--profile-id",
        help="safe Profile id (default: filename stem)",
    )
    return parser


def _preflight_mysql(profile, executor) -> None:
    if isinstance(executor, MySQLExecutor):
        connector = executor._connector_module or _load_mysql_connector()
        validate_mysql_config_schema(profile, executor.config, connector)


def _concise_answer(result: dict) -> dict:
    if result.get("status") != "OK":
        status = result.get("status", "ERROR")
        return {
            "status": (
                "safe_failure"
                if status in {"NEED_CLARIFICATION", "BLOCKED"}
                else "error"
            ),
            "reason_code": _result_reason_code(result),
            "reason": result.get("reason", "unknown failure"),
            "evidence": {},
        }
    if result.get("result_type") == "grouped":
        return {
            "status": "success",
            "profile_id": result["profile_id"],
            "metric": result["metric"],
            "filters": result["filters"],
            "result_type": "grouped",
            "group_by": result["group_by"],
            "time_range": result["time_range"],
            "order": result["order"],
            "limit": result["limit"],
            "rows": result["rows"],
            "verified": result["verified"],
            "evidence": {
                "row_count": result["row_count"],
                "result_key": result["metric"],
                "dimension_key": result["group_by"],
            },
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


def _result_reason_code(result: dict) -> str:
    status = result.get("status")
    reason = str(result.get("reason", "")).lower()
    if "unknown business metric" in reason:
        return "unknown_metric"
    if "multiple business metrics" in reason:
        return "ambiguous_metric"
    if "comparison is deferred" in reason:
        return "unsupported_comparison"
    if "time range" in reason or "date range" in reason or "month count" in reason:
        return "invalid_time_filter"
    if "grouping" in reason or "group-by" in reason:
        return "unsupported_grouping"
    if "ranking" in reason or "limit" in reason:
        return "invalid_ranking"
    if "unsafe sql-shaped" in reason or "mutation intent" in reason:
        return "unsafe_input"
    if (
        "unsupported filter" in reason
        or "unsupported region" in reason
        or (
            "unsupported" in reason
            and bool(result.get("semantic_plan", {}).get("filters"))
            and "compile_query" in result.get("trace", [])
        )
    ):
        return "unsupported_filter"
    if "scope" in reason or "multiple " in reason and " values" in reason:
        return "ambiguous_scope"
    if status == "BLOCKED":
        return "policy_blocked"
    if "verification failed" in reason:
        return "verification_failed"
    if status == "NEED_CLARIFICATION":
        return "semantic_clarification_required"
    return "execution_failed"


def _exception_result(error: Exception) -> dict:
    reason_code = getattr(error, "reason_code", None)
    hint = getattr(error, "hint", None)
    if reason_code is None and isinstance(error, ExecutionError):
        message = str(error)
        if "missing required environment variable" in message:
            reason_code = "database_configuration_missing"
            hint = "Set the required MYSQL_* environment variables."
        elif "unsupported DATA_AGENT_EXECUTOR" in message:
            reason_code = "database_backend_unsupported"
            hint = "Use DATA_AGENT_EXECUTOR=sqlite or mysql."
    result = {
        "status": "error",
        "reason_code": reason_code or "execution_error",
        "reason": str(error),
        "evidence": {},
    }
    if hint:
        result["hint"] = hint
    return result


def _new_cli(argv: list[str]) -> tuple[dict, int]:
    arguments = _parser().parse_args(argv)
    if arguments.command == "init-profile":
        profile = write_profile_scaffold(arguments.path, arguments.profile_id)
        return {
            "status": "created",
            "profile_id": profile.profile_id,
            "path": str(Path(arguments.path).resolve()),
            "next_steps": [
                "replace placeholder meaning/table/metric fields",
                f"python -m src.cli validate-profile --profile {arguments.path}",
                "use profiles/expenses.json as the filter example",
            ],
        }, 0
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
        if result["status"] != "OK":
            result = {**result, "reason_code": _result_reason_code(result)}
        return result, 0 if result["status"] == "OK" else 1
    executor = executor_from_env(_selected_db_path(arguments.db_path))
    _preflight_mysql(profile, executor)
    result = DataAgent(executor=executor, profile=profile).answer(question)
    concise = _concise_answer(result)
    return concise, 0 if concise["status"] == "success" else 1


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if values in (["-h"], ["--help"]):
        _parser().print_help()
        return 0
    try:
        if values and values[0] in COMMANDS:
            result, exit_code = _new_cli(values)
        else:
            question = " ".join(values) or "revenue"
            executor = executor_from_env(_selected_db_path(None))
            profile = _selected_profile(None)
            _preflight_mysql(profile, executor)
            result = DataAgent(executor=executor, profile=profile).answer(question)
            exit_code = 0 if result["status"] != "ERROR" else 2
    except (
        ExecutionError,
        ProfileScaffoldError,
        ProfileValidationError,
        SchemaInspectionError,
        SchemaValidationError,
    ) as error:
        result = _exception_result(error)
        exit_code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
