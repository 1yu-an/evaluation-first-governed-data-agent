import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


NUMERIC = "numeric"
EXACTLY_ONE = "exactly_one"
GROUPED = "grouped"


@dataclass(frozen=True)
class ResultContract:
    """Describe only the observable shape of one compiled query result."""

    expected_key: str
    expected_type: str
    nullable: bool
    cardinality: str
    dimension_key: str | None = None
    max_rows: int | None = None
    requested_limit: int | None = None
    order: str | None = None

    @classmethod
    def scalar_numeric(cls, expected_key: str) -> "ResultContract":
        return cls(
            expected_key=expected_key,
            expected_type=NUMERIC,
            nullable=False,
            cardinality=EXACTLY_ONE,
        )

    @classmethod
    def grouped_numeric(
        cls,
        expected_key: str,
        dimension_key: str,
        *,
        max_rows: int,
        requested_limit: int | None = None,
        order: str | None = None,
    ) -> "ResultContract":
        if not dimension_key:
            raise ValueError("grouped result requires a dimension key")
        if max_rows < 1:
            raise ValueError("grouped result max_rows must be positive")
        if requested_limit is not None and not 1 <= requested_limit <= max_rows:
            raise ValueError("grouped requested_limit must be within max_rows")
        if order not in {None, "dimension_asc", "metric_asc", "metric_desc"}:
            raise ValueError("unsupported grouped result order")
        return cls(
            expected_key=expected_key,
            expected_type=NUMERIC,
            nullable=False,
            cardinality=GROUPED,
            dimension_key=dimension_key,
            max_rows=max_rows,
            requested_limit=requested_limit,
            order=order,
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
    if contract.cardinality == GROUPED:
        return _verify_grouped(contract, evidence)
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
    if not _is_numeric(value):
        return _decision(False, "result value must be numeric")

    if not _is_finite(value):
        return _decision(False, "result value must be finite")
    return _decision(True, "ok")


def _is_numeric(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float, Decimal))


def _is_finite(value: int | float | Decimal) -> bool:
    return value.is_finite() if isinstance(value, Decimal) else math.isfinite(value)


def _verify_grouped(contract: ResultContract, evidence: Any) -> dict[str, Any]:
    if not isinstance(evidence, list):
        return _decision(False, "grouped evidence must be a list")
    if contract.dimension_key is None or contract.max_rows is None:
        return _decision(False, "grouped contract is incomplete")
    if len(evidence) > contract.max_rows:
        return _decision(False, "grouped row count exceeds maximum")
    if contract.requested_limit is not None and len(evidence) > contract.requested_limit:
        return _decision(False, "grouped row count exceeds requested limit")

    expected_keys = {contract.dimension_key, contract.expected_key}
    dimensions: list[str] = []
    metrics: list[int | float | Decimal] = []
    for row in evidence:
        if not isinstance(row, Mapping):
            return _decision(False, "each grouped row must be a mapping")
        if set(row) != expected_keys:
            return _decision(False, "grouped row columns do not match contract")
        dimension = row[contract.dimension_key]
        metric = row[contract.expected_key]
        if not isinstance(dimension, str) or not dimension.strip():
            return _decision(False, "grouped dimension value must be a non-empty string")
        if not _is_numeric(metric):
            return _decision(False, "grouped metric value must be numeric")
        if not _is_finite(metric):
            return _decision(False, "grouped metric value must be finite")
        dimensions.append(dimension)
        metrics.append(metric)

    if len(dimensions) != len(set(dimensions)):
        return _decision(False, "grouped dimension values must be unique")
    for index in range(1, len(evidence)):
        previous_dimension = dimensions[index - 1]
        current_dimension = dimensions[index]
        previous_metric = metrics[index - 1]
        current_metric = metrics[index]
        if contract.order == "dimension_asc" and previous_dimension > current_dimension:
            return _decision(False, "grouped rows violate dimension order")
        if contract.order == "metric_desc":
            if previous_metric < current_metric:
                return _decision(False, "grouped rows violate descending metric order")
            if previous_metric == current_metric and previous_dimension > current_dimension:
                return _decision(False, "grouped rows violate deterministic tie order")
        if contract.order == "metric_asc":
            if previous_metric > current_metric:
                return _decision(False, "grouped rows violate ascending metric order")
            if previous_metric == current_metric and previous_dimension > current_dimension:
                return _decision(False, "grouped rows violate deterministic tie order")
    return _decision(True, "ok")
