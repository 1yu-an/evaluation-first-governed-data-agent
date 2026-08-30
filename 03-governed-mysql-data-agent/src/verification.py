import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


NUMERIC = "numeric"
EXACTLY_ONE = "exactly_one"


@dataclass(frozen=True)
class ResultContract:
    """Describe only the observable shape of one compiled query result."""

    expected_key: str
    expected_type: str
    nullable: bool
    cardinality: str

    @classmethod
    def scalar_numeric(cls, expected_key: str) -> "ResultContract":
        return cls(
            expected_key=expected_key,
            expected_type=NUMERIC,
            nullable=False,
            cardinality=EXACTLY_ONE,
        )


def _decision(passed: bool, reason: str) -> dict[str, Any]:
    return {
        "method": "strict_result_contract",
        "passed": passed,
        "reason": reason,
    }


def verify_evidence(
    contract: ResultContract, evidence: Any
) -> dict[str, Any]:
    """Validate result shape and value type, not SQL business semantics."""
    if contract.cardinality != EXACTLY_ONE:
        return _decision(False, "unsupported result cardinality")
    if not isinstance(evidence, Mapping):
        return _decision(False, "evidence must be a mapping")
    if set(evidence) != {contract.expected_key}:
        return _decision(
            False,
            f"evidence must contain exactly the expected key: {contract.expected_key}",
        )

    value = evidence[contract.expected_key]
    if value is None:
        if contract.nullable:
            return _decision(True, "ok")
        return _decision(False, "result value must be non-null")

    if contract.expected_type != NUMERIC:
        return _decision(False, "unsupported result value type")
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return _decision(False, "result value must be numeric")

    finite = value.is_finite() if isinstance(value, Decimal) else math.isfinite(value)
    if not finite:
        return _decision(False, "result value must be finite")
    return _decision(True, "ok")
