"""Deterministic question-to-plan resolution driven by a Domain Profile."""

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .catalog import COUNT_INTENT, NET_OF
from .profile import CompositionPattern, DomainProfile, load_default_profile


PLAN_READY = "READY"
PLAN_NEEDS_CLARIFICATION = "NEED_CLARIFICATION"
ORDER_METRIC_ASC = "metric_asc"
ORDER_METRIC_DESC = "metric_desc"
MAX_ANALYTICS_LIMIT = 100
MAX_RELATIVE_MONTHS = 120


@dataclass(frozen=True)
class DateRange:
    dimension: str
    start_inclusive: date
    end_exclusive: date
    label: str

    def to_dict(self) -> dict[str, str]:
        return {
            "dimension": self.dimension,
            "start_inclusive": self.start_inclusive.isoformat(),
            "end_exclusive": self.end_exclusive.isoformat(),
            "label": self.label,
        }


@dataclass(frozen=True)
class SemanticPlan:
    metric: str | None
    filters: dict[str, str]
    status: str
    reason: str
    time_range: DateRange | None = None
    group_by: str | None = None
    order: str | None = None
    limit: int | None = None

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "filters": dict(self.filters),
            "time_range": (
                None if self.time_range is None else self.time_range.to_dict()
            ),
            "group_by": self.group_by,
            "order": self.order,
            "limit": self.limit,
            "status": self.status,
            "reason": self.reason,
        }


RESERVED_ADJACENT_VALUES = frozenset(
    {"and", "average", "avg", "by", "each", "every", "has", "mean", "per", "top"}
)
SQL_SHAPED_PATTERNS = (
    re.compile(r";|--|/\*|\*/"),
    re.compile(r"\bunion\s+select\b", re.I),
    re.compile(r"\bor\s+1\s*=\s*1\b", re.I),
    re.compile(r"\b(delete\s+from|drop\s+table|insert\s+into)\b", re.I),
    re.compile(r"\b(update\s+[a-z_][a-z0-9_]*\s+set)\b", re.I),
    re.compile(r"\b(alter\s+table|truncate\s+table)\b", re.I),
)


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
        if dimension.dimension_type != "categorical":
            continue
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
            if match and match.group(1).lower() not in RESERVED_ADJACENT_VALUES:
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


def _unsafe_query_reason(question: str, normalized: str) -> str | None:
    if any(pattern.search(question) for pattern in SQL_SHAPED_PATTERNS):
        return "unsafe SQL-shaped query text requires clarification / SQL 形态输入需要澄清"
    features = set(normalized.split())
    if features.intersection({"delete", "drop", "insert", "update", "alter", "truncate", "fix"}):
        return "write or mutation intent is not supported / 不支持写入或修改意图"
    return None


def _comparison_reason(normalized: str) -> str | None:
    padded = f" {normalized} "
    markers = (
        " compare ",
        " compared with ",
        " percentage change ",
        " versus ",
        " vs ",
    )
    if any(marker in padded for marker in markers):
        return "comparison is deferred to V3.1 / 比较分析延期到 V3.1"
    return None


def _analytics_enabled(profile: DomainProfile) -> bool:
    return bool(profile.intent_defaults) or any(
        dimension.groupable for dimension in profile.dimensions.values()
    )


def _dimension_labels(profile: DomainProfile) -> dict[str, str]:
    labels: dict[str, str] = {}
    for dimension in profile.dimensions.values():
        for label in (dimension.dimension_id, *dimension.adjacent_labels):
            normalized = label.lower().replace("_", " ")
            labels[normalized] = dimension.dimension_id
            if normalized.endswith("y"):
                labels[normalized[:-1] + "ies"] = dimension.dimension_id
            elif not normalized.endswith("s"):
                labels[normalized + "s"] = dimension.dimension_id
    return labels


def _ranking(
    question: str, normalized: str, enabled: bool
) -> tuple[str | None, int | None, bool, str | None]:
    if not enabled:
        return None, None, False, None
    lowered = question.lower()
    top = re.search(r"\btop\s+(-?\d+|[a-z]+)\b", lowered)
    highest = re.search(r"\b(highest|largest)\b", normalized)
    lowest = re.search(r"\b(lowest|smallest)\b", normalized)
    marker_count = sum(item is not None for item in (top, highest, lowest))
    if marker_count > 1:
        return None, None, True, "multiple ranking intents require clarification / 多个排序意图需要澄清"
    if top is not None:
        try:
            limit = int(top.group(1))
        except ValueError:
            return None, None, True, "ranking limit must be an integer / 排名数量必须是整数"
        if not 1 <= limit <= MAX_ANALYTICS_LIMIT:
            return (
                None,
                None,
                True,
                f"ranking limit must be between 1 and {MAX_ANALYTICS_LIMIT} / 排名数量超出范围",
            )
        return ORDER_METRIC_DESC, limit, True, None
    if highest is not None:
        return ORDER_METRIC_DESC, 1, True, None
    if lowest is not None:
        return ORDER_METRIC_ASC, 1, True, None
    return None, None, False, None


def _grouping(
    normalized: str,
    profile: DomainProfile,
    *,
    ranking: bool,
) -> tuple[str | None, str | None]:
    labels = _dimension_labels(profile)
    matches: set[str] = set()
    for label, dimension_id in labels.items():
        escaped = re.escape(label)
        if re.search(rf"\b(?:by|per)\s+{escaped}\b", normalized):
            matches.add(dimension_id)
        if re.search(rf"\b(?:each|every)\s+{escaped}\b", normalized):
            matches.add(dimension_id)
        if ranking and re.search(rf"\b{escaped}\b", normalized):
            matches.add(dimension_id)
        if re.search(rf"\b(?:by|per)\s+{escaped}\s+and\s+", normalized):
            return None, "multiple grouping dimensions are not supported / 不支持多个分组维度"
    if len(matches) > 1:
        return None, "multiple grouping dimensions are not supported / 不支持多个分组维度"
    group_by = next(iter(matches), None)
    for candidate in re.findall(r"\b(?:by|per)\s+([a-z][a-z0-9_]*)\b", normalized):
        if candidate in labels or candidate in {"average", "avg", "mean", "total", "sum"}:
            continue
        if group_by is None:
            return None, f"unknown grouping dimension: {candidate} / 未知分组维度"
    if ranking and group_by is None:
        return None, "ranking requires one approved grouping dimension / 排名需要一个获批分组维度"
    return group_by, None


def _month_start(reference: date, offset: int) -> date:
    absolute = reference.year * 12 + reference.month - 1 + offset
    return date(absolute // 12, absolute % 12 + 1, 1)


def _parsed_time_range(
    question: str,
    normalized: str,
    reference_date: date,
) -> tuple[tuple[date, date, str] | None, str | None]:
    lowered = question.lower()
    matches: list[tuple[date, date, str]] = []
    if re.search(r"\bthis\s+month\b", normalized):
        matches.append((_month_start(reference_date, 0), _month_start(reference_date, 1), "this_month"))
    if re.search(r"\blast\s+month\b", normalized):
        matches.append((_month_start(reference_date, -1), _month_start(reference_date, 0), "last_month"))
    past = re.search(r"\bpast\s+(\d+)\s+months?\b", normalized)
    if past:
        months = int(past.group(1))
        if not 1 <= months <= MAX_RELATIVE_MONTHS:
            return None, f"relative month count must be between 1 and {MAX_RELATIVE_MONTHS} / 月份数量超出范围"
        matches.append((_month_start(reference_date, -(months - 1)), _month_start(reference_date, 1), f"past_{months}_months"))
    explicit = re.search(
        r"\bbetween\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})\b",
        lowered,
    )
    if explicit:
        try:
            start = date.fromisoformat(explicit.group(1))
            inclusive_end = date.fromisoformat(explicit.group(2))
            end = inclusive_end + timedelta(days=1)
        except (ValueError, OverflowError):
            return None, "invalid ISO date range / 无效的 ISO 日期范围"
        if start > inclusive_end:
            return None, "date range start must not be after end / 日期范围起点不能晚于终点"
        matches.append((start, end, "explicit_range"))
    if len(matches) > 1:
        return None, "multiple time ranges require clarification / 多个时间范围需要澄清"
    if matches:
        return matches[0], None
    if re.search(r"\b(month|months|between)\b|\d{4}-\d{2}-\d{2}", normalized):
        return None, "unsupported or incomplete time range / 不支持或不完整的时间范围"
    return None, None


def _clarification(
    reason: str,
    *,
    metric: str | None = None,
    filters: dict[str, str] | None = None,
    time_range: DateRange | None = None,
    group_by: str | None = None,
    order: str | None = None,
    limit: int | None = None,
) -> SemanticPlan:
    return SemanticPlan(
        metric=metric,
        filters={} if filters is None else filters,
        status=PLAN_NEEDS_CLARIFICATION,
        reason=reason,
        time_range=time_range,
        group_by=group_by,
        order=order,
        limit=limit,
    )


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
    question: str,
    profile: DomainProfile | None = None,
    reference_date: date | None = None,
) -> SemanticPlan:
    """Resolve only semantics declared by the selected immutable profile."""
    selected = profile or load_default_profile()
    normalized, _ = _normalize_question(question, selected)
    unsafe_reason = _unsafe_query_reason(question, normalized)
    if unsafe_reason is not None:
        return _clarification(unsafe_reason)
    analytics_enabled = _analytics_enabled(selected)
    if analytics_enabled:
        comparison_reason = _comparison_reason(normalized)
        if comparison_reason is not None:
            return _clarification(comparison_reason)
    candidates = _metric_candidates(question, selected)
    order, limit, ranking, ranking_error = _ranking(
        question, normalized, analytics_enabled
    )
    if ranking_error is not None:
        return _clarification(ranking_error, order=order, limit=limit)
    if ranking and not re.search(r"\btop\b", normalized) and not candidates:
        approved_labels = {
            label
            for label, dimension_id in _dimension_labels(selected).items()
            if selected.dimensions[dimension_id].groupable
        }
        if not any(
            re.search(rf"\b{re.escape(label)}\b", normalized)
            for label in approved_labels
        ):
            order, limit, ranking = None, None, False
    group_by, group_error = _grouping(
        normalized, selected, ranking=ranking
    ) if analytics_enabled else (None, None)
    if group_error is not None:
        return _clarification(group_error, order=order, limit=limit)
    effective_date = reference_date or date.today()
    if not isinstance(effective_date, date):
        return _clarification("invalid reference date / 无效的参考日期")
    parsed_range, time_error = _parsed_time_range(
        question, normalized, effective_date
    )
    if time_error is not None:
        return _clarification(
            time_error, group_by=group_by, order=order, limit=limit
        )
    filters, dimension_error = _dimension_values(
        question, normalized, selected
    )
    if not candidates and (group_by is not None or ranking):
        features = set(normalized.split())
        if "median" not in features:
            intent = "ranking" if ranking else "group_by"
            default_metric = selected.intent_defaults.get(intent)
            if default_metric is not None:
                candidates = [default_metric]
    guard_reason = _guard_reason(question, filters, selected)

    if guard_reason is not None:
        return _clarification(
            guard_reason,
            filters=filters,
            group_by=group_by,
            order=order,
            limit=limit,
        )
    if not candidates:
        return _clarification(
            "unknown business metric / 未知业务指标",
            filters=filters,
            group_by=group_by,
            order=order,
            limit=limit,
        )
    if len(candidates) > 1:
        return _clarification(
            "multiple business metrics require clarification / 多个业务指标需要澄清",
            filters=filters,
            group_by=group_by,
            order=order,
            limit=limit,
        )

    metric = candidates[0]
    definition = selected.metric_catalog[metric]
    time_range = None
    if parsed_range is not None:
        date_dimensions = [
            dimension_id
            for dimension_id in definition.allowed_filters
            if selected.dimensions[dimension_id].dimension_type == "date"
        ]
        if len(date_dimensions) != 1:
            return _clarification(
                "metric does not have one approved date dimension / 指标没有唯一获批日期维度",
                metric=metric,
                filters=filters,
                group_by=group_by,
                order=order,
                limit=limit,
            )
        start, end, label = parsed_range
        time_range = DateRange(date_dimensions[0], start, end, label)
    if group_by is not None and group_by not in definition.allowed_group_by:
        return _clarification(
            f"unsupported group-by dimension: {group_by} / 不支持的分组维度",
            metric=metric,
            filters=filters,
            time_range=time_range,
            group_by=group_by,
            order=order,
            limit=limit,
        )
    if dimension_error is not None:
        return _clarification(
            dimension_error,
            metric=metric,
            filters=filters,
            time_range=time_range,
            group_by=group_by,
            order=order,
            limit=limit,
        )
    if any(
        marker in question
        for marker in selected.language.scope_ambiguity_markers
    ):
        return _clarification(
            "query scope requires clarification / 查询范围需要澄清",
            metric=metric,
            filters=filters,
            time_range=time_range,
            group_by=group_by,
            order=order,
            limit=limit,
        )
    return SemanticPlan(
        metric=metric,
        filters=filters,
        status=PLAN_READY,
        reason="ready / 可执行",
        time_range=time_range,
        group_by=group_by,
        order=order,
        limit=limit,
    )


def resolve_metric(question: str, profile: DomainProfile | None = None):
    """Backward-compatible metric view of an executable semantic plan."""
    plan = build_semantic_plan(question, profile)
    return plan.metric if plan.status == PLAN_READY else None
