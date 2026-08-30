from dataclasses import FrozenInstanceError

import pytest

import src.compiler as compiler_module
from src.catalog import (
    METRIC_CATALOG,
    METRIC_DEFINITIONS,
    CompilerStrategy,
)
from src.compiler import STRATEGY_COMPILERS, compile_plan
from src.semantic import PLAN_READY, SemanticPlan
from src.verification import ResultContract


def _ready_plan(metric: str) -> SemanticPlan:
    return SemanticPlan(
        metric=metric,
        filters={},
        status=PLAN_READY,
        reason="ready / 可执行",
    )


def test_catalog_is_immutable_and_metric_ids_are_unique():
    metric_ids = [definition.metric_id for definition in METRIC_DEFINITIONS]

    assert len(metric_ids) == len(set(metric_ids))
    assert set(metric_ids) == set(METRIC_CATALOG)
    with pytest.raises(TypeError):
        METRIC_CATALOG["invented"] = METRIC_DEFINITIONS[0]
    with pytest.raises(FrozenInstanceError):
        METRIC_DEFINITIONS[0].metric_id = "invented"


def test_every_metric_has_a_keyed_scalar_numeric_result_contract():
    for definition in METRIC_DEFINITIONS:
        contract = definition.result_contract

        assert isinstance(contract, ResultContract)
        assert contract.expected_key == definition.metric_id
        assert contract.expected_type == "numeric"
        assert contract.nullable is False
        assert contract.cardinality == "exactly_one"


def test_every_catalog_strategy_is_a_registered_allowlisted_strategy():
    catalog_strategies = {
        definition.compiler_strategy for definition in METRIC_DEFINITIONS
    }

    assert catalog_strategies == set(CompilerStrategy)
    assert set(STRATEGY_COMPILERS) == set(CompilerStrategy)


def test_resolver_metadata_is_embedded_in_existing_catalog_definitions():
    for definition in METRIC_DEFINITIONS:
        metadata = definition.resolver

        assert metadata.canonical_forms
        assert all(
            pattern.required_feature_groups
            for pattern in metadata.composition_patterns
        )


def test_compiler_dispatches_by_strategy_without_a_second_metric_sql_list():
    assert not hasattr(compiler_module, "BASE_SQL")
    assert set(STRATEGY_COMPILERS).isdisjoint(METRIC_CATALOG)

    for definition in METRIC_DEFINITIONS:
        compiled = compile_plan(_ready_plan(definition.metric_id))

        assert compiled.result_contract is definition.result_contract
