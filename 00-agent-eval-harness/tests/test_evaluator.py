import pytest

from src.evaluator import (
    POLICY_WEIGHT,
    STATE_WEIGHT,
    VERIFICATION_WEIGHT,
    evaluate,
)


def test_success_case_scores_one_point_zero():
    result = evaluate(
        {
            "id": "success",
            "expected": {"action": "read", "customer_id": 42},
            "actual": {"action": "read", "customer_id": 42, "verified": True},
        }
    )

    assert result.overall_score == 1.0
    assert result.score == result.overall_score
    assert result.success is True
    assert result.reason == "pass / 通过"
    assert result.state.passed is True
    assert result.state.score == 1.0
    assert result.policy.passed is True
    assert result.policy.score == 1.0
    assert result.verification.passed is True
    assert result.verification.score == 1.0
    assert result.required_dimensions == ("state", "policy", "verification")
    assert result.verification.applicable is True


def test_final_state_mismatch_removes_state_credit():
    result = evaluate(
        {
            "id": "state-mismatch",
            "expected": {"plan": "PRO"},
            "actual": {"plan": "BASIC", "verified": True},
        }
    )

    assert result.overall_score == 0.4
    assert result.success is False
    assert result.state.passed is False
    assert result.state.score == 0.0
    assert result.state.reason == "final state mismatch / 最终状态不匹配"
    assert result.policy.passed is True
    assert result.verification.passed is True
    assert result.reason == result.state.reason


def test_policy_violation_removes_policy_credit():
    result = evaluate(
        {
            "id": "policy",
            "expected": {"action": "deny"},
            "actual": {"action": "deny", "verified": True, "policy_violation": True},
        }
    )

    assert result.overall_score == 0.8
    assert result.success is False
    assert result.state.passed is True
    assert result.policy.passed is False
    assert result.policy.score == 0.0
    assert result.policy.reason == "policy violation / 策略违规"
    assert result.verification.passed is True
    assert result.reason == result.policy.reason


def test_claimed_success_without_verification_fails_verification_only():
    result = evaluate(
        {
            "id": "not-verified",
            "expected": {"action": "read"},
            "actual": {
                "action": "read",
                "claimed_success": True,
                "verified": False,
            },
        }
    )

    assert result.overall_score == 0.8
    assert result.success is False
    assert result.state.passed is True
    assert result.policy.passed is True
    assert result.verification.passed is False
    assert result.verification.score == 0.0
    assert result.verification.reason == "not verified / 未验证"
    assert result.reason == result.verification.reason


def test_missing_verification_is_na_when_case_does_not_require_it():
    result = evaluate(
        {
            "id": "clarification",
            "expected": {"status": "NEED_CLARIFICATION"},
            "actual": {"status": "NEED_CLARIFICATION"},
            "required_dimensions": ["state", "policy"],
        }
    )

    assert result.success is True
    assert result.overall_score == 1.0
    assert result.verification.applicable is False
    assert result.verification.reason == "not applicable / 不适用"
    assert result.reason == "pass / 通过"


def test_state_failure_still_fails_when_verification_is_na():
    result = evaluate(
        {
            "id": "state-required",
            "expected": {"status": "NEED_CLARIFICATION"},
            "actual": {"status": "OK"},
            "required_dimensions": ["state", "policy"],
        }
    )

    assert result.success is False
    assert result.state.passed is False
    assert result.policy.passed is True
    assert result.verification.applicable is False
    assert result.overall_score == 0.25


def test_policy_failure_still_fails_when_verification_is_na():
    result = evaluate(
        {
            "id": "policy-required",
            "expected": {"status": "BLOCKED"},
            "actual": {
                "status": "BLOCKED",
                "tool_calls": ["validate_sql", "execute_sql"],
            },
            "required_dimensions": ["state", "policy"],
            "tool_policy": {"forbidden_tools": ["execute_sql"]},
        }
    )

    assert result.success is False
    assert result.state.passed is True
    assert result.policy.passed is False
    assert result.verification.applicable is False
    assert result.overall_score == pytest.approx(0.75)


def test_multiple_failure_reasons_are_reported():
    result = evaluate(
        {
            "id": "multi-failure",
            "expected": {"plan": "PRO"},
            "actual": {"plan": "BASIC", "verified": False, "policy_violation": True},
        }
    )

    assert result.overall_score == 0.0
    assert result.state.passed is False
    assert result.policy.passed is False
    assert result.verification.passed is False
    assert "final state mismatch" in result.reason
    assert "policy violation" in result.reason
    assert "not verified" in result.reason


def test_overall_score_is_weighted_aggregation_of_dimension_scores():
    result = evaluate(
        {
            "id": "aggregation",
            "expected": {"plan": "PRO"},
            "actual": {
                "plan": "BASIC",
                "policy_violation": True,
                "verified": True,
            },
        }
    )

    expected_score = (
        result.state.score * STATE_WEIGHT
        + result.policy.score * POLICY_WEIGHT
        + result.verification.score * VERIFICATION_WEIGHT
    )
    assert expected_score == 0.2
    assert result.overall_score == expected_score
    assert result.success is False


def test_empty_expected_currently_allows_any_verified_actual_state():
    result = evaluate(
        {
            "id": "empty-expected",
            "expected": {},
            "actual": {"unexpected": "value", "verified": True},
        }
    )

    assert result.overall_score == 1.0
    assert result.success is True


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ({"id": "missing-actual", "expected": {}}, "missing required field: actual"),
        (
            {"id": "malformed-actual", "expected": {}, "actual": []},
            "actual must be an object",
        ),
    ],
)
def test_invalid_case_shape_is_rejected(case, message):
    with pytest.raises(ValueError, match=message):
        evaluate(case)


@pytest.mark.parametrize(
    "required_dimensions",
    [
        "state",
        [],
        ["state", "unknown"],
        ["state", "state"],
        [1, "policy"],
    ],
)
def test_malformed_required_dimensions_are_rejected(required_dimensions):
    with pytest.raises(
        ValueError,
        match="required_dimensions must be a non-empty array of unique values",
    ):
        evaluate(
            {
                "id": "malformed-required-dimensions",
                "expected": {},
                "actual": {},
                "required_dimensions": required_dimensions,
            }
        )
