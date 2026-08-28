from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


STATE_WEIGHT = 0.6
POLICY_WEIGHT = 0.2
VERIFICATION_WEIGHT = 0.2
PASS_REASON = "pass / 通过"
NOT_APPLICABLE_REASON = "not applicable / 不适用"
DEFAULT_REQUIRED_DIMENSIONS = ("state", "policy", "verification")
DIMENSION_WEIGHTS = {
    "state": STATE_WEIGHT,
    "policy": POLICY_WEIGHT,
    "verification": VERIFICATION_WEIGHT,
}


@dataclass(frozen=True)
class DimensionResult:
    score: float
    passed: bool
    reason: str
    applicable: bool = True


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    state: DimensionResult
    policy: DimensionResult
    verification: DimensionResult
    category: str = "uncategorized"
    required_dimensions: tuple[str, ...] = DEFAULT_REQUIRED_DIMENSIONS
    overall_score: float = field(init=False)
    success: bool = field(init=False)

    def __post_init__(self) -> None:
        dimensions = {
            "state": self.state,
            "policy": self.policy,
            "verification": self.verification,
        }
        required_weight = sum(
            DIMENSION_WEIGHTS[name] for name in self.required_dimensions
        )
        overall_score = sum(
            dimensions[name].score * DIMENSION_WEIGHTS[name]
            for name in self.required_dimensions
        ) / required_weight
        object.__setattr__(
            self,
            "success",
            all(dimensions[name].passed for name in self.required_dimensions),
        )
        object.__setattr__(self, "overall_score", overall_score)

    @property
    def score(self) -> float:
        """Backward-compatible alias for the aggregated score."""
        return self.overall_score

    @property
    def reason(self) -> str:
        """Backward-compatible summary composed from failed dimensions."""
        failures = []
        dimensions = {
            "state": self.state,
            "policy": self.policy,
            "verification": self.verification,
        }
        for name in self.required_dimensions:
            dimension = dimensions[name]
            if not dimension.passed:
                failures.append(dimension.reason)
        return "; ".join(failures) or PASS_REASON


def _required_mapping(case: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    if field_name not in case:
        raise ValueError(f"missing required field: {field_name}")
    value = case[field_name]
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _string_list(
    container: Mapping[str, Any], field_name: str, qualified_name: str
) -> list[str]:
    value = container.get(field_name, [])
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"{qualified_name} must be an array of non-empty strings")
    return value


def _tool_trace(actual: Mapping[str, Any]) -> list[str]:
    return _string_list(actual, "tool_calls", "actual.tool_calls")


def _tool_policy(case: Mapping[str, Any]) -> Mapping[str, Any]:
    if "tool_policy" not in case:
        return {}
    value = case["tool_policy"]
    if not isinstance(value, Mapping):
        raise ValueError("tool_policy must be an object")
    return value


def _tool_order(tool_policy: Mapping[str, Any]) -> list[tuple[str, str]]:
    value = tool_policy.get("tool_order", [])
    if not isinstance(value, list):
        raise ValueError("tool_policy.tool_order must be an array of tool pairs")

    rules = []
    for rule in value:
        if (
            not isinstance(rule, list)
            or len(rule) != 2
            or any(not isinstance(tool, str) or not tool for tool in rule)
        ):
            raise ValueError(
                "tool_policy.tool_order entries must be two non-empty tool names"
            )
        before, after = rule
        if before == after:
            raise ValueError(
                "tool_policy.tool_order entries must name two different tools"
            )
        rules.append((before, after))
    return rules


def _required_dimensions(case: Mapping[str, Any]) -> tuple[str, ...]:
    if "required_dimensions" not in case:
        return DEFAULT_REQUIRED_DIMENSIONS
    value = case["required_dimensions"]
    allowed = set(DEFAULT_REQUIRED_DIMENSIONS)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(name, str) or name not in allowed for name in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(
            "required_dimensions must be a non-empty array of unique values from: "
            "state, policy, verification"
        )
    return tuple(value)


def _apply_dimension_contract(
    name: str,
    result: DimensionResult,
    required_dimensions: tuple[str, ...],
) -> DimensionResult:
    if name in required_dimensions:
        return result
    return DimensionResult(
        score=0.0,
        passed=False,
        reason=NOT_APPLICABLE_REASON,
        applicable=False,
    )


def _evaluate_policy(
    case: Mapping[str, Any], actual: Mapping[str, Any]
) -> DimensionResult:
    failures = []
    if actual.get("policy_violation") is True:
        failures.append("policy violation / 策略违规")

    trace = _tool_trace(actual)
    tool_policy = _tool_policy(case)
    required_tools = _string_list(
        tool_policy, "required_tools", "tool_policy.required_tools"
    )
    forbidden_tools = _string_list(
        tool_policy, "forbidden_tools", "tool_policy.forbidden_tools"
    )

    missing_required = [tool for tool in required_tools if tool not in trace]
    if missing_required:
        failures.append(
            "missing required tools: " + ", ".join(missing_required)
            + " / 缺少必需工具"
        )

    used_forbidden = [tool for tool in forbidden_tools if tool in trace]
    if used_forbidden:
        failures.append(
            "forbidden tools used: " + ", ".join(used_forbidden)
            + " / 使用了禁止工具"
        )

    for before, after in _tool_order(tool_policy):
        missing_for_order = [tool for tool in (before, after) if tool not in trace]
        if missing_for_order:
            failures.append(
                f"tool order requires {before} before {after}; missing: "
                + ", ".join(missing_for_order)
                + " / 顺序约束缺少工具"
            )
        elif trace.index(before) >= trace.index(after):
            failures.append(
                f"wrong tool order: {before} must precede {after} / 工具顺序错误"
            )

    passed = not failures
    return DimensionResult(
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=(
            "no policy violation / 无策略违规"
            if passed
            else "; ".join(failures)
        ),
    )


def evaluate(case: Mapping[str, Any]) -> EvalResult:
    """Evaluate observable state, policy, and verification independently."""
    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("id must be a non-empty string")
    category = case.get("category", "uncategorized")
    if not isinstance(category, str) or not category:
        raise ValueError("category must be a non-empty string")

    expected = _required_mapping(case, "expected")
    actual = _required_mapping(case, "actual")
    required_dimensions = _required_dimensions(case)

    state_passed = all(actual.get(key) == value for key, value in expected.items())
    verification_passed = actual.get("verified") is True

    state = _apply_dimension_contract("state", DimensionResult(
        score=1.0 if state_passed else 0.0,
        passed=state_passed,
        reason=(
            "state matches expected / 状态符合预期"
            if state_passed
            else "final state mismatch / 最终状态不匹配"
        ),
    ), required_dimensions)
    policy = _apply_dimension_contract(
        "policy", _evaluate_policy(case, actual), required_dimensions
    )
    verification = _apply_dimension_contract("verification", DimensionResult(
        score=1.0 if verification_passed else 0.0,
        passed=verification_passed,
        reason=(
            "verified / 已验证"
            if verification_passed
            else "not verified / 未验证"
        ),
    ), required_dimensions)

    return EvalResult(
        case_id=case_id,
        state=state,
        policy=policy,
        verification=verification,
        category=category,
        required_dimensions=required_dimensions,
    )
