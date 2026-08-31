"""Strict external Domain Profile loading for the governed data agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .verification import ResultContract


PROFILE_VERSION = 1
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FIXED_LITERAL = re.compile(r"^[A-Za-z0-9_.-]+$")
DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[1] / "profiles" / "demo.json"
)


class ProfileValidationError(ValueError):
    """A profile is malformed, unsafe, or internally inconsistent."""

    reason_code = "profile_validation_failed"
    hint = (
        "Fix the reported JSON path(s), then run validate-profile again."
    )

    def __init__(self, issues: str | list[str]):
        self.issues = [issues] if isinstance(issues, str) else list(issues)
        super().__init__("profile validation failed: " + "; ".join(self.issues))


class ProfileScaffoldError(ValueError):
    """A Profile scaffold could not be created safely."""

    def __init__(self, reason_code: str, message: str, hint: str):
        self.reason_code = reason_code
        self.hint = hint
        super().__init__(message)


@dataclass(frozen=True)
class CompositionPattern:
    required_feature_groups: tuple[frozenset[str], ...]


@dataclass(frozen=True)
class ResolverMetadata:
    canonical_forms: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    cjk_aliases: tuple[str, ...] = ()
    composition_patterns: tuple[CompositionPattern, ...] = ()


@dataclass(frozen=True)
class GuardRule:
    rule_id: str
    reason: str
    all_features: frozenset[str] = frozenset()
    any_features: frozenset[str] = frozenset()
    ignore_if_dimensions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LanguageDefinition:
    token_normalization: Mapping[str, str]
    scope_ambiguity_markers: tuple[str, ...]
    guard_rules: tuple[GuardRule, ...]


@dataclass(frozen=True)
class DimensionDefinition:
    dimension_id: str
    phrases: Mapping[str, str]
    adjacent_labels: tuple[str, ...] = ()

    @property
    def allowed_values(self) -> frozenset[str]:
        return frozenset(self.phrases.values())


@dataclass(frozen=True)
class Source:
    table: str
    alias: str


@dataclass(frozen=True)
class FixedPredicate:
    column: str
    value: str


@dataclass(frozen=True)
class FilterBinding:
    column: str


@dataclass(frozen=True)
class AggregateOperation:
    operation_type: str
    aggregate: str
    source: Source
    column: str | None
    round_digits: int | None
    coalesce_zero: bool
    fixed_predicates: tuple[FixedPredicate, ...]
    filter_bindings: Mapping[str, FilterBinding]


@dataclass(frozen=True)
class SumSide:
    source: Source
    column: str
    fixed_predicates: tuple[FixedPredicate, ...]


@dataclass(frozen=True)
class JoinSide:
    source_column: str
    target_column: str


@dataclass(frozen=True)
class FilterJoin:
    table: str
    alias: str
    value_column: str
    left_join: JoinSide
    right_join: JoinSide


@dataclass(frozen=True)
class DifferenceOfSumsOperation:
    operation_type: str
    left: SumSide
    right: SumSide
    round_digits: int
    filter_joins: Mapping[str, FilterJoin]


MetricOperation = AggregateOperation | DifferenceOfSumsOperation


@dataclass(frozen=True)
class ResultKeyDefinition:
    mode: str


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    business_meaning: str
    resolver: ResolverMetadata
    result_contract: ResultContract
    operation: MetricOperation
    allowed_filters: frozenset[str]
    result_key: ResultKeyDefinition

    @property
    def compiler_strategy(self) -> str:
        """Compatibility view of the finite operation discriminator."""
        return self.operation.operation_type


@dataclass(frozen=True)
class DomainProfile:
    profile_version: int
    profile_id: str
    description: str
    language: LanguageDefinition
    dimensions: Mapping[str, DimensionDefinition]
    metric_definitions: tuple[MetricDefinition, ...]
    metric_catalog: Mapping[str, MetricDefinition]


def _object(
    value: Any,
    path: str,
    *,
    required: set[str],
    optional: set[str] = frozenset(),
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileValidationError(f"{path}: expected object")
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - set(optional))
    issues = [f"{path}.{key}: required field is missing" for key in missing]
    issues += [f"{path}.{key}: unknown field" for key in unknown]
    if issues:
        raise ProfileValidationError(issues)
    return value


def _string(value: Any, path: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileValidationError(f"{path}: expected non-empty string")
    result = value.strip()
    if identifier and not IDENTIFIER.fullmatch(result):
        raise ProfileValidationError(
            f"{path}: unsafe identifier syntax {result!r}"
        )
    return result


def _string_list(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ProfileValidationError(f"{path}: expected array")
    result = tuple(_string(item, f"{path}[{index}]") for index, item in enumerate(value))
    normalized = [item.lower() for item in result]
    if len(normalized) != len(set(normalized)):
        raise ProfileValidationError(f"{path}: duplicate values")
    return result


def _mapping(value: Any, path: str) -> Mapping[str, str]:
    if not isinstance(value, dict):
        raise ProfileValidationError(f"{path}: expected object")
    result: dict[str, str] = {}
    for key, item in value.items():
        phrase = _string(key, f"{path}.<key>").lower()
        if phrase in result:
            raise ProfileValidationError(f"{path}.{phrase}: duplicate phrase")
        result[phrase] = _string(item, f"{path}.{key}")
    return MappingProxyType(result)


def _source(value: Any, path: str) -> Source:
    data = _object(value, path, required={"table", "alias"})
    return Source(
        table=_string(data["table"], f"{path}.table", identifier=True),
        alias=_string(data["alias"], f"{path}.alias", identifier=True),
    )


def _predicates(value: Any, path: str) -> tuple[FixedPredicate, ...]:
    if not isinstance(value, list):
        raise ProfileValidationError(f"{path}: expected array")
    result = []
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        data = _object(item, item_path, required={"column", "value"})
        literal = _string(data["value"], f"{item_path}.value")
        if not FIXED_LITERAL.fullmatch(literal):
            raise ProfileValidationError(
                f"{item_path}.value: unsafe fixed literal {literal!r}"
            )
        result.append(
            FixedPredicate(
                column=_string(
                    data["column"], f"{item_path}.column", identifier=True
                ),
                value=literal,
            )
        )
    return tuple(result)


def _composition_patterns(value: Any, path: str) -> tuple[CompositionPattern, ...]:
    if not isinstance(value, list):
        raise ProfileValidationError(f"{path}: expected array")
    patterns = []
    for pattern_index, item in enumerate(value):
        item_path = f"{path}[{pattern_index}]"
        if not isinstance(item, list) or not item:
            raise ProfileValidationError(f"{item_path}: expected non-empty array")
        groups = []
        for group_index, group in enumerate(item):
            group_path = f"{item_path}[{group_index}]"
            values = _string_list(group, group_path)
            if not values:
                raise ProfileValidationError(f"{group_path}: expected non-empty array")
            groups.append(frozenset(value.lower() for value in values))
        patterns.append(CompositionPattern(tuple(groups)))
    return tuple(patterns)


def _language(value: Any, path: str) -> LanguageDefinition:
    data = _object(
        value,
        path,
        required={
            "token_normalization",
            "scope_ambiguity_markers",
            "guard_rules",
        },
    )
    normalization = _mapping(data["token_normalization"], f"{path}.token_normalization")
    rules_value = data["guard_rules"]
    if not isinstance(rules_value, list):
        raise ProfileValidationError(f"{path}.guard_rules: expected array")
    rules = []
    rule_ids = set()
    for index, item in enumerate(rules_value):
        rule_path = f"{path}.guard_rules[{index}]"
        rule = _object(
            item,
            rule_path,
            required={"id", "reason", "all_features", "any_features"},
            optional={"ignore_if_dimensions"},
        )
        rule_id = _string(rule["id"], f"{rule_path}.id", identifier=True)
        if rule_id in rule_ids:
            raise ProfileValidationError(f"{rule_path}.id: duplicate id {rule_id!r}")
        rule_ids.add(rule_id)
        all_features = frozenset(
            item.lower()
            for item in _string_list(rule["all_features"], f"{rule_path}.all_features")
        )
        any_features = frozenset(
            item.lower()
            for item in _string_list(rule["any_features"], f"{rule_path}.any_features")
        )
        if not all_features and not any_features:
            raise ProfileValidationError(
                f"{rule_path}: at least one feature condition is required"
            )
        ignored = frozenset(
            _string_list(
                rule.get("ignore_if_dimensions", []),
                f"{rule_path}.ignore_if_dimensions",
            )
        )
        rules.append(
            GuardRule(
                rule_id=rule_id,
                reason=_string(rule["reason"], f"{rule_path}.reason"),
                all_features=all_features,
                any_features=any_features,
                ignore_if_dimensions=ignored,
            )
        )
    return LanguageDefinition(
        token_normalization=normalization,
        scope_ambiguity_markers=_string_list(
            data["scope_ambiguity_markers"], f"{path}.scope_ambiguity_markers"
        ),
        guard_rules=tuple(rules),
    )


def _dimensions(value: Any, path: str) -> Mapping[str, DimensionDefinition]:
    if not isinstance(value, list):
        raise ProfileValidationError(f"{path}: expected array")
    result = {}
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        data = _object(
            item,
            item_path,
            required={"id", "phrases"},
            optional={"adjacent_labels"},
        )
        dimension_id = _string(data["id"], f"{item_path}.id", identifier=True)
        if dimension_id in result:
            raise ProfileValidationError(
                f"{item_path}.id: duplicate dimension id {dimension_id!r}"
            )
        phrases = _mapping(data["phrases"], f"{item_path}.phrases")
        for phrase, db_value in phrases.items():
            if not FIXED_LITERAL.fullmatch(db_value):
                raise ProfileValidationError(
                    f"{item_path}.phrases.{phrase}: unsafe database value {db_value!r}"
                )
        result[dimension_id] = DimensionDefinition(
            dimension_id=dimension_id,
            phrases=phrases,
            adjacent_labels=_string_list(
                data.get("adjacent_labels", []), f"{item_path}.adjacent_labels"
            ),
        )
    return MappingProxyType(result)


def _aggregate_operation(value: dict[str, Any], path: str) -> AggregateOperation:
    data = _object(
        value,
        path,
        required={
            "type",
            "aggregate",
            "source",
            "column",
            "round_digits",
            "coalesce_zero",
            "fixed_predicates",
            "filter_bindings",
        },
    )
    aggregate = _string(data["aggregate"], f"{path}.aggregate").lower()
    if aggregate not in {"count", "sum", "avg", "max"}:
        raise ProfileValidationError(
            f"{path}.aggregate: unsupported aggregate {aggregate!r}; "
            "supported values: avg, count, max, sum"
        )
    column_value = data["column"]
    if column_value is None:
        column = None
    else:
        column = _string(column_value, f"{path}.column", identifier=True)
    if aggregate == "count" and column is not None:
        raise ProfileValidationError(f"{path}.column: count requires null")
    if aggregate != "count" and column is None:
        raise ProfileValidationError(f"{path}.column: {aggregate} requires a column")
    round_digits = data["round_digits"]
    if round_digits is not None and (
        isinstance(round_digits, bool)
        or not isinstance(round_digits, int)
        or not 0 <= round_digits <= 6
    ):
        raise ProfileValidationError(f"{path}.round_digits: expected null or integer 0..6")
    coalesce_zero = data["coalesce_zero"]
    if not isinstance(coalesce_zero, bool):
        raise ProfileValidationError(f"{path}.coalesce_zero: expected boolean")
    if coalesce_zero and aggregate not in {"count", "sum"}:
        raise ProfileValidationError(
            f"{path}.coalesce_zero: supported only for count or sum"
        )
    if not isinstance(data["filter_bindings"], dict):
        raise ProfileValidationError(f"{path}.filter_bindings: expected object")
    bindings = {}
    for dimension_id, item in data["filter_bindings"].items():
        binding_path = f"{path}.filter_bindings.{dimension_id}"
        _string(dimension_id, f"{path}.filter_bindings.<key>", identifier=True)
        binding = _object(item, binding_path, required={"column"})
        bindings[dimension_id] = FilterBinding(
            column=_string(binding["column"], f"{binding_path}.column", identifier=True)
        )
    return AggregateOperation(
        operation_type="aggregate",
        aggregate=aggregate,
        source=_source(data["source"], f"{path}.source"),
        column=column,
        round_digits=round_digits,
        coalesce_zero=coalesce_zero,
        fixed_predicates=_predicates(data["fixed_predicates"], f"{path}.fixed_predicates"),
        filter_bindings=MappingProxyType(bindings),
    )


def _sum_side(value: Any, path: str) -> SumSide:
    data = _object(value, path, required={"source", "column", "fixed_predicates"})
    return SumSide(
        source=_source(data["source"], f"{path}.source"),
        column=_string(data["column"], f"{path}.column", identifier=True),
        fixed_predicates=_predicates(data["fixed_predicates"], f"{path}.fixed_predicates"),
    )


def _join_side(value: Any, path: str) -> JoinSide:
    data = _object(value, path, required={"source_column", "target_column"})
    return JoinSide(
        source_column=_string(
            data["source_column"], f"{path}.source_column", identifier=True
        ),
        target_column=_string(
            data["target_column"], f"{path}.target_column", identifier=True
        ),
    )


def _difference_operation(
    value: dict[str, Any], path: str
) -> DifferenceOfSumsOperation:
    data = _object(
        value,
        path,
        required={"type", "left", "right", "round_digits", "filter_joins"},
    )
    round_digits = data["round_digits"]
    if (
        isinstance(round_digits, bool)
        or not isinstance(round_digits, int)
        or not 0 <= round_digits <= 6
    ):
        raise ProfileValidationError(f"{path}.round_digits: expected integer 0..6")
    if not isinstance(data["filter_joins"], dict):
        raise ProfileValidationError(f"{path}.filter_joins: expected object")
    joins = {}
    for dimension_id, item in data["filter_joins"].items():
        join_path = f"{path}.filter_joins.{dimension_id}"
        _string(dimension_id, f"{path}.filter_joins.<key>", identifier=True)
        join = _object(
            item,
            join_path,
            required={"table", "alias", "value_column", "left_join", "right_join"},
        )
        joins[dimension_id] = FilterJoin(
            table=_string(join["table"], f"{join_path}.table", identifier=True),
            alias=_string(join["alias"], f"{join_path}.alias", identifier=True),
            value_column=_string(
                join["value_column"], f"{join_path}.value_column", identifier=True
            ),
            left_join=_join_side(join["left_join"], f"{join_path}.left_join"),
            right_join=_join_side(join["right_join"], f"{join_path}.right_join"),
        )
    operation = DifferenceOfSumsOperation(
        operation_type="difference_of_sums",
        left=_sum_side(data["left"], f"{path}.left"),
        right=_sum_side(data["right"], f"{path}.right"),
        round_digits=round_digits,
        filter_joins=MappingProxyType(joins),
    )
    for dimension_id, join in operation.filter_joins.items():
        if join.alias in {operation.left.source.alias, operation.right.source.alias}:
            raise ProfileValidationError(
                f"{path}.filter_joins.{dimension_id}.alias: conflicts with source alias"
            )
    return operation


def _operation(value: Any, path: str) -> MetricOperation:
    if not isinstance(value, dict):
        raise ProfileValidationError(f"{path}: expected object")
    operation_type = _string(value.get("type"), f"{path}.type")
    if operation_type == "aggregate":
        return _aggregate_operation(value, path)
    if operation_type == "difference_of_sums":
        return _difference_operation(value, path)
    raise ProfileValidationError(
        f"{path}.type: unsupported operation {operation_type!r}; "
        "supported values: aggregate, difference_of_sums"
    )


def _metrics(
    value: Any,
    path: str,
    dimensions: Mapping[str, DimensionDefinition],
) -> tuple[MetricDefinition, ...]:
    if not isinstance(value, list) or not value:
        raise ProfileValidationError(f"{path}: expected non-empty array")
    result = []
    metric_ids = set()
    explicit_forms: dict[str, str] = {}
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        data = _object(
            item,
            item_path,
            required={
                "id",
                "meaning",
                "canonical_forms",
                "synonyms",
                "cjk_aliases",
                "composition_patterns",
                "allowed_dimensions",
                "result_key",
                "operation",
            },
        )
        metric_id = _string(data["id"], f"{item_path}.id", identifier=True)
        if metric_id in metric_ids:
            raise ProfileValidationError(f"{item_path}.id: duplicate metric id {metric_id!r}")
        metric_ids.add(metric_id)
        canonical_forms = _string_list(
            data["canonical_forms"], f"{item_path}.canonical_forms"
        )
        aliases = _string_list(data["synonyms"], f"{item_path}.synonyms")
        cjk_aliases = _string_list(data["cjk_aliases"], f"{item_path}.cjk_aliases")
        patterns = _composition_patterns(
            data["composition_patterns"], f"{item_path}.composition_patterns"
        )
        if not canonical_forms and not aliases and not cjk_aliases and not patterns:
            raise ProfileValidationError(f"{item_path}: metric has no resolver evidence")
        for form in canonical_forms + aliases + cjk_aliases:
            normalized_form = form.strip().lower().replace("_", " ")
            previous = explicit_forms.get(normalized_form)
            if previous is not None and previous != metric_id:
                raise ProfileValidationError(
                    f"{item_path}: resolver phrase {form!r} is already owned by metric {previous!r}"
                )
            explicit_forms[normalized_form] = metric_id
        allowed_filters = frozenset(
            _string_list(data["allowed_dimensions"], f"{item_path}.allowed_dimensions")
        )
        unknown_dimensions = sorted(allowed_filters - set(dimensions))
        if unknown_dimensions:
            raise ProfileValidationError(
                f"{item_path}.allowed_dimensions: unknown dimensions {unknown_dimensions}"
            )
        result_key_data = _object(
            data["result_key"], f"{item_path}.result_key", required={"mode"}
        )
        result_key_mode = _string(
            result_key_data["mode"], f"{item_path}.result_key.mode"
        )
        if result_key_mode not in {"metric", "dimension_value_prefix"}:
            raise ProfileValidationError(
                f"{item_path}.result_key.mode: unsupported mode "
                f"{result_key_mode!r}; supported values: "
                "dimension_value_prefix, metric"
            )
        if result_key_mode == "dimension_value_prefix" and len(allowed_filters) != 1:
            raise ProfileValidationError(
                f"{item_path}.result_key.mode: dimension_value_prefix requires exactly one allowed dimension"
            )
        operation = _operation(data["operation"], f"{item_path}.operation")
        operation_dimensions = (
            set(operation.filter_bindings)
            if isinstance(operation, AggregateOperation)
            else set(operation.filter_joins)
        )
        if operation_dimensions != set(allowed_filters):
            raise ProfileValidationError(
                f"{item_path}.operation: filter definitions must exactly match allowed_dimensions"
            )
        result.append(
            MetricDefinition(
                metric_id=metric_id,
                business_meaning=_string(data["meaning"], f"{item_path}.meaning"),
                resolver=ResolverMetadata(
                    canonical_forms=canonical_forms,
                    aliases=aliases,
                    cjk_aliases=cjk_aliases,
                    composition_patterns=patterns,
                ),
                result_contract=ResultContract.scalar_numeric(metric_id),
                operation=operation,
                allowed_filters=allowed_filters,
                result_key=ResultKeyDefinition(result_key_mode),
            )
        )
    return tuple(result)


def validate_profile_data(data: Any, source: str = "<memory>") -> DomainProfile:
    root = _object(
        data,
        "$",
        required={"profile_version", "id", "language", "dimensions", "metrics"},
        optional={"description"},
    )
    if (
        isinstance(root["profile_version"], bool)
        or not isinstance(root["profile_version"], int)
        or root["profile_version"] != PROFILE_VERSION
    ):
        raise ProfileValidationError(
            f"$.profile_version: expected {PROFILE_VERSION}, got {root['profile_version']!r}"
        )
    dimensions = _dimensions(root["dimensions"], "$.dimensions")
    language = _language(root["language"], "$.language")
    for rule_index, rule in enumerate(language.guard_rules):
        unknown = sorted(rule.ignore_if_dimensions - set(dimensions))
        if unknown:
            raise ProfileValidationError(
                f"$.language.guard_rules[{rule_index}].ignore_if_dimensions: "
                f"unknown dimensions {unknown}"
            )
    metrics = _metrics(root["metrics"], "$.metrics", dimensions)
    profile_id = _string(root["id"], "$.id", identifier=True)
    description = root.get("description", "")
    if not isinstance(description, str):
        raise ProfileValidationError("$.description: expected string")
    return DomainProfile(
        profile_version=PROFILE_VERSION,
        profile_id=profile_id,
        description=description.strip(),
        language=language,
        dimensions=dimensions,
        metric_definitions=metrics,
        metric_catalog=MappingProxyType({item.metric_id: item for item in metrics}),
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileValidationError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_profile(path: str | Path) -> DomainProfile:
    profile_path = Path(path)
    try:
        text = profile_path.read_text(encoding="utf-8")
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except ProfileValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileValidationError(f"{profile_path}: cannot load JSON: {error}") from error
    return validate_profile_data(data, str(profile_path))


def profile_scaffold_data(profile_id: str) -> dict[str, Any]:
    """Return one legal, minimal Profile without inferring business semantics."""
    if not isinstance(profile_id, str) or not IDENTIFIER.fullmatch(profile_id):
        raise ProfileScaffoldError(
            "invalid_profile_id",
            f"invalid Profile id: {profile_id!r}",
            "Use --profile-id with letters, digits, and underscores; do not start with a digit.",
        )
    data = {
        "profile_version": PROFILE_VERSION,
        "id": profile_id,
        "description": "Replace with this personal domain's purpose.",
        "language": {
            "token_normalization": {},
            "scope_ambiguity_markers": [],
            "guard_rules": [],
        },
        "dimensions": [],
        "metrics": [
            {
                "id": "row_count",
                "meaning": "Count rows in replace_table; replace this meaning.",
                "canonical_forms": ["row_count", "row count"],
                "synonyms": [],
                "cjk_aliases": [],
                "composition_patterns": [],
                "allowed_dimensions": [],
                "result_key": {"mode": "metric"},
                "operation": {
                    "type": "aggregate",
                    "aggregate": "count",
                    "source": {"table": "replace_table", "alias": "t"},
                    "column": None,
                    "round_digits": None,
                    "coalesce_zero": False,
                    "fixed_predicates": [],
                    "filter_bindings": {},
                },
            }
        ],
    }
    validate_profile_data(data, "<generated scaffold>")
    return data


def write_profile_scaffold(
    path: str | Path, profile_id: str | None = None
) -> DomainProfile:
    """Create a validated JSON scaffold exclusively; never overwrite a file."""
    target = Path(path)
    selected_id = profile_id if profile_id is not None else target.stem
    data = profile_scaffold_data(selected_id)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
    except FileExistsError as error:
        raise ProfileScaffoldError(
            "profile_target_exists",
            f"refusing to overwrite existing Profile: {target}",
            "Choose a new path or move the existing file explicitly.",
        ) from error
    except OSError as error:
        raise ProfileScaffoldError(
            "profile_scaffold_write_failed",
            f"could not write Profile scaffold {target}: {error}",
            "Check the parent path and filesystem permissions.",
        ) from error
    return load_profile(target)


@lru_cache(maxsize=1)
def load_default_profile() -> DomainProfile:
    return load_profile(DEFAULT_PROFILE_PATH)


def required_schema(profile: DomainProfile) -> dict[str, frozenset[str]]:
    tables: dict[str, set[str]] = {}

    def add(table: str, *columns: str | None) -> None:
        tables.setdefault(table, set()).update(column for column in columns if column)

    for metric in profile.metric_definitions:
        operation = metric.operation
        if isinstance(operation, AggregateOperation):
            add(
                operation.source.table,
                operation.column,
                *(item.column for item in operation.fixed_predicates),
                *(item.column for item in operation.filter_bindings.values()),
            )
            continue
        for side in (operation.left, operation.right):
            add(
                side.source.table,
                side.column,
                *(item.column for item in side.fixed_predicates),
            )
        for join in operation.filter_joins.values():
            add(operation.left.source.table, join.left_join.source_column)
            add(operation.right.source.table, join.right_join.source_column)
            add(
                join.table,
                join.value_column,
                join.left_join.target_column,
                join.right_join.target_column,
            )
    return {table: frozenset(columns) for table, columns in sorted(tables.items())}
