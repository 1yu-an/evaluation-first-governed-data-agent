from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class EvalResult:
    case_id: str
    success: bool
    score: float
    reason: str


def evaluate(case: Dict[str, Any]) -> EvalResult:
    """Compare observable state, not model claims. / 比较可观察状态，而不是模型自述。"""
    expected = case.get("expected", {})
    actual = case.get("actual", {})
    policy_ok = actual.get("policy_violation") is not True
    state_ok = all(actual.get(k) == v for k, v in expected.items())
    verification_ok = actual.get("verified", False) is True
    score = (0.6 if state_ok else 0.0) + (0.2 if policy_ok else 0.0) + (0.2 if verification_ok else 0.0)
    success = score == 1.0
    reasons = []
    if not state_ok: reasons.append("final state mismatch / 最终状态不匹配")
    if not policy_ok: reasons.append("policy violation / 策略违规")
    if not verification_ok: reasons.append("not verified / 未验证")
    return EvalResult(case["id"], success, score, "; ".join(reasons) or "pass / 通过")
