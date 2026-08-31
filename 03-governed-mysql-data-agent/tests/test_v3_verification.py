from decimal import Decimal

import pytest

from src.verification import ResultContract, verify_evidence


def _contract(**overrides):
    values = {
        "expected_key": "total_expenses",
        "dimension_key": "category",
        "max_rows": 100,
        "requested_limit": None,
        "order": "dimension_asc",
    }
    values.update(overrides)
    return ResultContract.grouped_numeric(**values)


def test_valid_and_empty_grouped_evidence_verify():
    contract = _contract()

    assert verify_evidence(
        contract,
        [
            {"category": "food", "total_expenses": Decimal("47.50")},
            {"category": "housing", "total_expenses": 900.0},
            {"category": "transport", "total_expenses": 30},
        ],
    )["passed"] is True
    assert verify_evidence(contract, []) == {
        "method": "strict_result_contract",
        "passed": True,
        "reason": "ok",
    }


@pytest.mark.parametrize(
    ("evidence", "reason"),
    [
        ({"category": "food", "total_expenses": 1}, "must be a list"),
        ([{"category": "food"}], "columns"),
        ([{"category": "food", "total_expenses": 1, "extra": 2}], "columns"),
        ([{"category": 7, "total_expenses": 1}], "dimension value"),
        ([{"category": "food", "total_expenses": "1"}], "must be numeric"),
        ([{"category": "food", "total_expenses": True}], "must be numeric"),
        ([{"category": "food", "total_expenses": float("nan")}], "must be finite"),
        (
            [
                {"category": "food", "total_expenses": 1},
                {"category": "food", "total_expenses": 2},
            ],
            "must be unique",
        ),
    ],
)
def test_grouped_evidence_rejects_wrong_shape_types_and_values(evidence, reason):
    decision = verify_evidence(_contract(), evidence)

    assert decision["passed"] is False
    assert reason in decision["reason"]


def test_grouped_evidence_enforces_maximum_and_requested_limit():
    too_many = [
        {"category": f"c{index:03d}", "total_expenses": index}
        for index in range(101)
    ]
    over_requested = too_many[:4]

    assert "exceeds maximum" in verify_evidence(_contract(), too_many)["reason"]
    assert "requested limit" in verify_evidence(
        _contract(requested_limit=3), over_requested
    )["reason"]


@pytest.mark.parametrize(
    ("order", "rows", "reason"),
    [
        (
            "dimension_asc",
            [
                {"category": "transport", "total_expenses": 30},
                {"category": "food", "total_expenses": 47.5},
            ],
            "dimension order",
        ),
        (
            "metric_desc",
            [
                {"category": "food", "total_expenses": 47.5},
                {"category": "housing", "total_expenses": 900},
            ],
            "descending metric order",
        ),
        (
            "metric_asc",
            [
                {"category": "housing", "total_expenses": 900},
                {"category": "food", "total_expenses": 47.5},
            ],
            "ascending metric order",
        ),
        (
            "metric_desc",
            [
                {"category": "transport", "total_expenses": 30},
                {"category": "food", "total_expenses": 30},
            ],
            "tie order",
        ),
    ],
)
def test_grouped_evidence_enforces_declared_order(order, rows, reason):
    decision = verify_evidence(_contract(order=order), rows)

    assert decision["passed"] is False
    assert reason in decision["reason"]
