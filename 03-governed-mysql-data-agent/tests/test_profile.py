import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.profile import (
    ProfileValidationError,
    load_default_profile,
    load_profile,
    required_schema,
    validate_profile_data,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPENSES_PATH = PROJECT_ROOT / "profiles" / "expenses.json"


def _expenses_data():
    return json.loads(EXPENSES_PATH.read_text(encoding="utf-8"))


def test_default_and_expenses_profiles_load_as_immutable_catalogs():
    demo = load_default_profile()
    expenses = load_profile(EXPENSES_PATH)

    assert demo.profile_id == "demo"
    assert len(demo.metric_definitions) == 7
    assert set(expenses.metric_catalog) == {
        "total_expenses",
        "expense_count",
        "average_expense",
    }
    assert expenses.intent_defaults == {
        "group_by": "total_expenses",
        "ranking": "total_expenses",
    }
    assert expenses.dimensions["category"].groupable is True
    assert expenses.dimensions["date"].dimension_type == "date"
    assert expenses.dimensions["date"].column == "spent_on"
    with pytest.raises(TypeError):
        expenses.metric_catalog["invented"] = expenses.metric_definitions[0]


def test_required_schema_is_derived_from_operations_not_duplicated_config():
    assert required_schema(load_profile(EXPENSES_PATH)) == {
        "expenses": frozenset({"amount", "category", "spent_on"})
    }
    assert required_schema(load_default_profile()) == {
        "orders": frozenset({"id", "status", "total", "region"}),
        "payments": frozenset({"amount", "order_id", "status"}),
        "refunds": frozenset({"amount", "order_id", "status"}),
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.update(profile_version=2), "profile_version"),
        (lambda data: data.update(profile_version=True), "profile_version"),
        (lambda data: data.update(unknown=True), "unknown field"),
        (
            lambda data: data["metrics"][0].update(id="bad;drop"),
            "unsafe identifier",
        ),
        (
            lambda data: data["metrics"][0].update(
                allowed_dimensions=["missing"]
            ),
            "unknown dimensions",
        ),
        (
            lambda data: data["metrics"][0]["operation"].update(
                aggregate="median"
            ),
            "unsupported aggregate",
        ),
        (
            lambda data: data["metrics"][2]["operation"].update(
                coalesce_zero=True
            ),
            "supported only for count or sum",
        ),
    ],
)
def test_static_validation_rejects_unsafe_or_inconsistent_profiles(
    mutation, message
):
    data = _expenses_data()
    mutation(data)

    with pytest.raises(ProfileValidationError, match=message):
        validate_profile_data(data)


def test_duplicate_json_keys_and_malformed_json_fail_with_actionable_errors(
    tmp_path,
):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"profile_version":1,"profile_version":1}', encoding="utf-8")
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ProfileValidationError, match="duplicate JSON key"):
        load_profile(duplicate)
    with pytest.raises(ProfileValidationError, match="cannot load JSON"):
        load_profile(malformed)


def test_fixed_predicate_cannot_become_a_sql_injection_channel():
    data = deepcopy(_expenses_data())
    operation = data["metrics"][0]["operation"]
    operation["fixed_predicates"] = [
        {"column": "category", "value": "food' OR 1=1 --"}
    ]

    with pytest.raises(ProfileValidationError, match="unsafe fixed literal"):
        validate_profile_data(data)


def test_explicit_resolver_phrase_cannot_belong_to_two_metrics():
    data = _expenses_data()
    data["metrics"][1]["synonyms"].append("total expenses")

    with pytest.raises(ProfileValidationError, match="already owned"):
        validate_profile_data(data)


def test_invalid_aggregate_lists_supported_repair_values():
    data = _expenses_data()
    data["metrics"][0]["operation"]["aggregate"] = "average"

    with pytest.raises(ProfileValidationError) as captured:
        validate_profile_data(data)

    message = str(captured.value)
    assert "supported values: avg, count, max, sum" in message
    assert captured.value.reason_code == "profile_validation_failed"
    assert captured.value.hint


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda data: data["dimensions"][0].update(column="category;drop"),
            "unsafe identifier",
        ),
        (
            lambda data: data["dimensions"][3].update(type="sql_date"),
            "unsupported dimension type",
        ),
        (
            lambda data: data["dimensions"][3].update(groupable=True),
            "requires a categorical dimension",
        ),
        (
            lambda data: data["metrics"][0].update(allowed_group_by=["date"]),
            "not groupable",
        ),
        (
            lambda data: data["metrics"][1].update(default_intents=["ranking"]),
            "already owned",
        ),
        (
            lambda data: data["metrics"][0].update(raw_group_by="category"),
            "unknown field",
        ),
    ],
)
def test_v3_profile_extensions_reject_unsafe_or_inconsistent_data(
    mutation, message
):
    data = _expenses_data()
    mutation(data)

    with pytest.raises(ProfileValidationError, match=message):
        validate_profile_data(data)
