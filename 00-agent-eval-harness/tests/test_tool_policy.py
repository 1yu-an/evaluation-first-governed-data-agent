import pytest

from src.evaluator import evaluate


def _case(*, tool_calls=None, tool_policy=None):
    case = {
        "id": "tool-policy-case",
        "category": "tool-policy-test",
        "expected": {"status": "completed"},
        "actual": {"status": "completed", "verified": True},
    }
    if tool_calls is not None:
        case["actual"]["tool_calls"] = tool_calls
    if tool_policy is not None:
        case["tool_policy"] = tool_policy
    return case


def test_required_tools_present_pass_policy():
    result = evaluate(
        _case(
            tool_calls=["search", "read", "verify_result"],
            tool_policy={"required_tools": ["read", "verify_result"]},
        )
    )

    assert result.category == "tool-policy-test"
    assert result.policy.passed is True
    assert result.success is True


def test_required_tool_missing_fails_with_tool_name():
    result = evaluate(
        _case(
            tool_calls=["search", "read"],
            tool_policy={"required_tools": ["read", "verify_result"]},
        )
    )

    assert result.state.passed is True
    assert result.policy.passed is False
    assert result.verification.passed is True
    assert result.success is False
    assert "missing required tools: verify_result" in result.policy.reason


def test_forbidden_tool_absent_passes_policy():
    result = evaluate(
        _case(
            tool_calls=["search", "read"],
            tool_policy={"forbidden_tools": ["delete", "shell_exec"]},
        )
    )

    assert result.policy.passed is True
    assert result.success is True


def test_forbidden_tool_used_fails_policy_only():
    result = evaluate(
        _case(
            tool_calls=["read", "delete"],
            tool_policy={"forbidden_tools": ["delete", "shell_exec"]},
        )
    )

    assert result.state.passed is True
    assert result.policy.passed is False
    assert result.verification.passed is True
    assert result.success is False
    assert "forbidden tools used: delete" in result.policy.reason


def test_required_satisfied_but_forbidden_used_still_fails():
    result = evaluate(
        _case(
            tool_calls=["read", "verify_result", "shell_exec"],
            tool_policy={
                "required_tools": ["verify_result"],
                "forbidden_tools": ["shell_exec"],
            },
        )
    )

    assert "missing required tools" not in result.policy.reason
    assert "forbidden tools used: shell_exec" in result.policy.reason
    assert result.policy.passed is False


def test_correct_tool_order_passes():
    result = evaluate(
        _case(
            tool_calls=["authenticate", "query_database", "verify"],
            tool_policy={
                "tool_order": [
                    ["authenticate", "query_database"],
                    ["query_database", "verify"],
                ]
            },
        )
    )

    assert result.policy.passed is True
    assert result.success is True


def test_reversed_tool_order_fails_policy():
    result = evaluate(
        _case(
            tool_calls=["query_database", "authenticate", "verify"],
            tool_policy={"tool_order": [["authenticate", "query_database"]]},
        )
    )

    assert result.state.passed is True
    assert result.policy.passed is False
    assert result.verification.passed is True
    assert "wrong tool order: authenticate must precede query_database" in (
        result.policy.reason
    )


def test_order_rule_with_missing_endpoint_fails_with_clear_reason():
    result = evaluate(
        _case(
            tool_calls=["authenticate"],
            tool_policy={"tool_order": [["authenticate", "query_database"]]},
        )
    )

    assert result.policy.passed is False
    assert "tool order requires authenticate before query_database" in (
        result.policy.reason
    )
    assert "missing: query_database" in result.policy.reason


def test_legacy_case_without_tool_rules_remains_compatible():
    result = evaluate(
        {
            "id": "legacy-case",
            "expected": {"action": "read"},
            "actual": {"action": "read", "verified": True},
        }
    )

    assert result.category == "uncategorized"
    assert result.policy.passed is True
    assert result.success is True


@pytest.mark.parametrize(
    ("case", "message"),
    [
        (_case(tool_calls="search"), "actual.tool_calls must be an array"),
        (_case(tool_calls=["search", {}]), "actual.tool_calls must be an array"),
        (_case(tool_policy=[]), "tool_policy must be an object"),
        (
            _case(tool_policy={"required_tools": "verify"}),
            "tool_policy.required_tools must be an array",
        ),
        (
            _case(tool_policy={"tool_order": [["authenticate"]]}),
            "tool_policy.tool_order entries must be two non-empty tool names",
        ),
        (
            _case(tool_policy={"tool_order": [["query", "query"]]}),
            "tool_policy.tool_order entries must name two different tools",
        ),
    ],
)
def test_malformed_tool_policy_input_is_rejected(case, message):
    with pytest.raises(ValueError, match=message):
        evaluate(case)
