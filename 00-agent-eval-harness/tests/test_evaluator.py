from src.evaluator import evaluate


def test_success_case_scores_one_point_zero():
    result = evaluate(
        {
            "id": "success",
            "expected": {"action": "read", "customer_id": 42},
            "actual": {"action": "read", "customer_id": 42, "verified": True},
        }
    )

    assert result.score == 1.0
    assert result.success is True
    assert result.reason == "pass / 通过"


def test_final_state_mismatch_removes_state_credit():
    result = evaluate(
        {
            "id": "state-mismatch",
            "expected": {"plan": "PRO"},
            "actual": {"plan": "BASIC", "verified": True},
        }
    )

    assert result.score == 0.4
    assert result.success is False
    assert "final state mismatch" in result.reason


def test_policy_violation_removes_policy_credit():
    result = evaluate(
        {
            "id": "policy",
            "expected": {"action": "deny"},
            "actual": {"action": "deny", "verified": True, "policy_violation": True},
        }
    )

    assert result.score == 0.8
    assert result.success is False
    assert "policy violation" in result.reason


def test_not_verified_removes_verification_credit():
    result = evaluate(
        {
            "id": "not-verified",
            "expected": {"action": "read"},
            "actual": {"action": "read", "verified": False},
        }
    )

    assert result.score == 0.8
    assert result.success is False
    assert "not verified" in result.reason


def test_multiple_failure_reasons_are_reported():
    result = evaluate(
        {
            "id": "multi-failure",
            "expected": {"plan": "PRO"},
            "actual": {"plan": "BASIC", "verified": False, "policy_violation": True},
        }
    )

    assert result.score == 0.0
    assert "final state mismatch" in result.reason
    assert "policy violation" in result.reason
    assert "not verified" in result.reason


def test_empty_expected_currently_allows_any_verified_actual_state():
    result = evaluate(
        {
            "id": "empty-expected",
            "expected": {},
            "actual": {"unexpected": "value", "verified": True},
        }
    )

    assert result.score == 1.0
    assert result.success is True
