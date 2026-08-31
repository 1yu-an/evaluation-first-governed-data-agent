"""Deterministic question-to-plan resolution driven by a Domain Profile."""

import re
from dataclasses import asdict, dataclass

from .catalog import COUNT_INTENT, NET_OF
from .profile import CompositionPattern, DomainProfile, load_default_profile


PLAN_READY = "READY"
PLAN_NEEDS_CLARIFICATION = "NEED_CLARIFICATION"


@dataclass(frozen=True)
class SemanticPlan:
    metric: str | None
    filters: dict[str, str]
    status: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_question(
    question: str, profile: DomainProfile
) -> tuple[str, frozenset[str]]:
    lowered = question.lower().replace("_", " ")
    raw_tokens = re.findall(r"[a-z0-9]+", lowered)
    normalized = " ".join(raw_tokens)
    tokens = [
        profile.language.token_normalization.get(token, token)
        for token in raw_tokens
    ]
    features = set(tokens)
    if "count" in features or "number" in features or "how many" in normalized:
        features.add(COUNT_INTENT)
    if "net of" in normalized:
        features.add(NET_OF)
    return normalized, frozenset(features)


def _contains_form(
    question: str, normalized: str, form: str, profile: DomainProfile
) -> bool:
    if any(ord(character) > 127 for character in form):
        return form.lower() in question.lower()
    if "_" in form:
        return re.search(
            rf"(?<![a-z0-9_]){re.escape(form.lower())}(?![a-z0-9_])",
            question.lower(),
        ) is not None
    normalized_form, _ = _normalize_question(form, profile)
    return f" {normalized_form} " in f" {normalized} "


def _rule_matches(
    rule: CompositionPattern, features: frozenset[str]
) -> bool:
    return all(
        features.intersection(group)
        for group in rule.required_feature_groups
    )


def _metric_candidates(question: str, profile: DomainProfile) -> list[str]:
    normalized, features = _normalize_question(question, profile)
    candidates = set()
    for definition in profile.metric_definitions:
        metadata = definition.resolver
        forms = (
            metadata.canonical_forms
            + metadata.aliases
            + metadata.cjk_aliases
        )
        if any(
            _contains_form(question, normalized, form, profile)
            for form in forms
        ):
            candidates.add(definition.metric_id)
        if any(
            _rule_matches(pattern, features)
            for pattern in metadata.composition_patterns
        ):
            candidates.add(definition.metric_id)
    return [
        definition.metric_id
        for definition in profile.metric_definitions
        if definition.metric_id in candidates
    ]


def _dimension_values(
    question: str, normalized: str, profile: DomainProfile
) -> tuple[dict[str, str], str | None]:
    filters: dict[str, str] = {}
    padded = f" {normalized} "
    for dimension in profile.dimensions.values():
        values: list[str] = []
        for phrase, value in sorted(
            dimension.phrases.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if _contains_form(question, normalized, phrase, profile):
                values.append(value)
        for label in dimension.adjacent_labels:
            normalized_label, _ = _normalize_question(label, profile)
            escaped = re.escape(normalized_label)
            after = re.search(
                rf"\b{escaped}\s+([a-z][a-z0-9_-]*)\b", padded, re.I
            )
            before = re.search(
                rf"\b([a-z][a-z0-9_-]*)\s+{escaped}\b", padded, re.I
            )
            match = after or before
            if match:
                values.append(match.group(1).lower())
        distinct = list(dict.fromkeys(values))
        if len(distinct) > 1:
            return filters, (
                f"multiple {dimension.dimension_id} values require clarification / "
                "多个过滤值需要澄清"
            )
        if distinct:
            filters[dimension.dimension_id] = distinct[0]
    return filters, None


def _guard_reason(
    question: str, filters: dict[str, str], profile: DomainProfile
) -> str | None:
    _, features = _normalize_question(question, profile)
    for rule in profile.language.guard_rules:
        if rule.ignore_if_dimensions.intersection(filters):
            continue
        if not rule.all_features.issubset(features):
            continue
        if rule.any_features and not rule.any_features.intersection(features):
            continue
        return rule.reason
    return None


def build_semantic_plan(
    question: str, profile: DomainProfile | None = None
) -> SemanticPlan:
    """Resolve only semantics declared by the selected immutable profile."""
    selected = profile or load_default_profile()
    normalized, _ = _normalize_question(question, selected)
    filters, dimension_error = _dimension_values(
        question, normalized, selected
    )
    candidates = _metric_candidates(question, selected)
    guard_reason = _guard_reason(question, filters, selected)

    if guard_reason is not None:
        return SemanticPlan(
            metric=None,
            filters=filters,
            status=PLAN_NEEDS_CLARIFICATION,
            reason=guard_reason,
        )
    if not candidates:
        return SemanticPlan(
            metric=None,
            filters=filters,
            status=PLAN_NEEDS_CLARIFICATION,
            reason="unknown business metric / 未知业务指标",
        )
    if len(candidates) > 1:
        return SemanticPlan(
            metric=None,
            filters=filters,
            status=PLAN_NEEDS_CLARIFICATION,
            reason="multiple business metrics require clarification / 多个业务指标需要澄清",
        )

    metric = candidates[0]
    if dimension_error is not None:
        return SemanticPlan(
            metric=metric,
            filters=filters,
            status=PLAN_NEEDS_CLARIFICATION,
            reason=dimension_error,
        )
    if any(
        marker in question
        for marker in selected.language.scope_ambiguity_markers
    ):
        return SemanticPlan(
            metric=metric,
            filters=filters,
            status=PLAN_NEEDS_CLARIFICATION,
            reason="query scope requires clarification / 查询范围需要澄清",
        )
    return SemanticPlan(
        metric=metric,
        filters=filters,
        status=PLAN_READY,
        reason="ready / 可执行",
    )


def resolve_metric(question: str, profile: DomainProfile | None = None):
    """Backward-compatible metric view of an executable semantic plan."""
    plan = build_semantic_plan(question, profile)
    return plan.metric if plan.status == PLAN_READY else None
