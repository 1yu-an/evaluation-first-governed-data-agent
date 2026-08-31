from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

from .evaluator import EvalResult, evaluate


class Runtime03(Protocol):
    def answer(self, question: str) -> Mapping[str, Any]: ...

    def evaluate_sql_policy(self, sql: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class IntegrationExecution:
    case: dict[str, Any]
    raw_result: dict[str, Any]
    eval_case: dict[str, Any]
    result: EvalResult


def _load_package(project_root: Path) -> tuple[str, ModuleType]:
    source_root = project_root.resolve() / "src"
    init_path = source_root / "__init__.py"
    if not init_path.is_file():
        raise ValueError(f"03 package not found: {init_path}")

    digest = hashlib.sha256(str(source_root).encode("utf-8")).hexdigest()[:12]
    package_name = f"_governed_mysql_agent_{digest}"
    if package_name in sys.modules:
        return package_name, sys.modules[package_name]

    spec = importlib.util.spec_from_file_location(
        package_name,
        init_path,
        submodule_search_locations=[str(source_root)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load 03 package from {init_path}")
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    spec.loader.exec_module(package)
    return package_name, package


class GovernedMySQLRuntime:
    """Thin external caller for project 03's public Python interfaces."""

    def __init__(self, project_root: str | Path, db_path: str | Path):
        package_name, _ = _load_package(Path(project_root))
        agent_module = importlib.import_module(f"{package_name}.agent")
        policy_module = importlib.import_module(f"{package_name}.policy")
        demo_module = importlib.import_module(f"{package_name}.demo")
        self._agent = agent_module.DataAgent(str(db_path))
        self._evaluate_sql_policy = policy_module.evaluate_sql_policy
        self._initialize_demo = demo_module.initialize_demo
        self.db_path = Path(db_path)

    def initialize_demo(self) -> Path:
        return self._initialize_demo(self.db_path)

    def answer(self, question: str) -> Mapping[str, Any]:
        return self._agent.answer(question)

    def evaluate_sql_policy(self, sql: str) -> Mapping[str, Any]:
        return self._evaluate_sql_policy(sql)


class GovernedExpensesRuntime:
    """External V3 caller using the real expenses Profile and SQLite fixture."""

    def __init__(
        self,
        project_root: str | Path,
        db_path: str | Path,
        reference_date: date,
    ):
        if not isinstance(reference_date, date):
            raise ValueError("reference_date must be a date")
        root = Path(project_root)
        package_name, _ = _load_package(root)
        agent_module = importlib.import_module(f"{package_name}.agent")
        profile_module = importlib.import_module(f"{package_name}.profile")
        demo_module = importlib.import_module(f"{package_name}.demo")
        profile = profile_module.load_profile(
            root / "profiles" / "expenses.json"
        )
        self._agent = agent_module.DataAgent(
            str(db_path),
            profile=profile,
            reference_date=reference_date,
        )
        self._initialize_expenses = demo_module.initialize_expenses
        self.db_path = Path(db_path)

    def initialize_expenses(self) -> Path:
        return self._initialize_expenses(self.db_path)

    def answer(self, question: str) -> Mapping[str, Any]:
        return self._agent.answer(question)


def load_integration_cases(path: str | Path) -> list[dict[str, Any]]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("03 integration corpus must be a JSON array")
    cases = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("03 integration cases must be objects")
        if "actual" in item:
            raise ValueError("03 integration cases must not contain actual")
        cases.append(item)
    return cases


def adapt_raw_result(raw_result: Mapping[str, Any]) -> dict[str, Any]:
    """Translate 03 field names without judging whether the run succeeded."""
    actual = dict(raw_result)
    if "trace" in actual:
        actual["tool_calls"] = actual.pop("trace")
    return actual


def _execute_request(
    request: Mapping[str, Any], runtime: Runtime03
) -> Mapping[str, Any]:
    target = request.get("target")
    if target == "agent.answer":
        question = request.get("question")
        if not isinstance(question, str):
            raise ValueError("agent.answer request.question must be a string")
        return runtime.answer(question)
    if target == "policy.evaluate_sql":
        sql = request.get("sql")
        if not isinstance(sql, str):
            raise ValueError("policy.evaluate_sql request.sql must be a string")
        return runtime.evaluate_sql_policy(sql)
    raise ValueError(f"unsupported 03 integration target: {target}")


def run_integration_case(
    case: Mapping[str, Any], runtime: Runtime03
) -> IntegrationExecution:
    if "actual" in case:
        raise ValueError("03 integration cases must not contain actual")
    request = case.get("request")
    if not isinstance(request, Mapping):
        raise ValueError("03 integration case request must be an object")

    raw_result = dict(_execute_request(request, runtime))
    eval_case = {
        key: value
        for key, value in case.items()
        if key
        in {
            "id",
            "category",
            "expected",
            "expected_success",
            "required_dimensions",
            "tool_policy",
        }
    }
    eval_case["actual"] = adapt_raw_result(raw_result)
    result = evaluate(eval_case)
    return IntegrationExecution(
        case=dict(case),
        raw_result=raw_result,
        eval_case=eval_case,
        result=result,
    )


def run_integration_cases(
    cases: Sequence[Mapping[str, Any]], runtime: Runtime03
) -> list[IntegrationExecution]:
    return [run_integration_case(case, runtime) for case in cases]
