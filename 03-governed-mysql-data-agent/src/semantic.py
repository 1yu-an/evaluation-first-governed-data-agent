import re
from dataclasses import asdict, dataclass

from .catalog import COUNT_INTENT, METRIC_DEFINITIONS, NET_OF, CompositionPattern


PLAN_READY = "READY"
PLAN_NEEDS_CLARIFICATION = "NEED_CLARIFICATION"


@dataclass(frozen=True)
class GuardRule:
    """Stop expressions whose modifiers change or obscure metric semantics."""

    reason: str
    all_features: frozenset[str] = frozenset()
    any_features: frozenset[str] = frozenset()


SINGULAR_FORMS = {
    "amounts": "amount",
    "baskets": "basket",
    "orders": "order",
    "payments": "payment",
    "purchases": "purchase",
    "refunds": "refund",
    "sales": "sale",
    "values": "value",
}
GUARD_RULES = (
    GuardRule(
        reason="unsupported derived metric modifier / 不支持的派生指标修饰词",
        any_features=frozenset(
            {"before", "forecast", "growth", "margin", "rate"}
        ),
    ),
    GuardRule(
        reason="unsupported per-unit semantics / 不支持的单位化语义",
        all_features=frozenset({"per"}),
    ),
    GuardRule(
        reason="turnover meaning requires clarification / turnover 含义需要澄清",
        all_features=frozenset({"turnover"}),
    ),
    GuardRule(
        reason="money-made meaning requires clarification / money made 含义需要澄清",
        all_features=frozenset({"money"}),
        any_features=frozenset({"make", "made"}),
    ),
    GuardRule(
        reason="fulfilled state meaning requires clarification / fulfilled 状态含义需要澄清",
        all_features=frozenset({"fulfilled"}),
        any_features=frozenset({"order", "purchase"}),
    ),
    GuardRule(
        reason="negated metric semantics require clarification / 否定指标语义需要澄清",
        any_features=frozenset({"exclude", "excluding", "not", "without"}),
    ),
    GuardRule(
        reason="payment/refund count is not a governed metric / 付款或退款计数不是受治理指标",
        all_features=frozenset({COUNT_INTENT}),
        any_features=frozenset({"payment", "refund"}),
    ),
    GuardRule(
        reason="pending payment/refund amount is not a governed metric / 待处理付款或退款金额不是受治理指标",
        all_features=frozenset({"pending"}),
        any_features=frozenset({"payment", "refund"}),
    ),
    GuardRule(
        reason="failed payment/refund amount is not a governed metric / 失败付款或退款金额不是受治理指标",
        all_features=frozenset({"failed"}),
        any_features=frozenset({"payment", "refund"}),
    ),
)

ALIASES = {
    alias: definition.metric_id
    for definition in METRIC_DEFINITIONS
    for alias in definition.resolver.cjk_aliases
}

UNSPECIFIED_SCOPE_MARKERS = ("一下",)
REGION_PATTERNS = (
    re.compile(r"\b([a-z][a-z0-9_-]*)\s+region\b", re.I),
    re.compile(r"\bregion\s+([a-z][a-z0-9_-]*)\b", re.I),
)
STATUS_PATTERNS = (
    re.compile(r"\bstatus\s*(?:=|is)?\s*([a-z][a-z0-9_-]*)\b", re.I),
    re.compile(r"\b([a-z][a-z0-9_-]*)\s+status\b", re.I),
)


@dataclass(frozen=True)
class SemanticPlan:
    metric: str | None
    filters: dict[str, str]
    status: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_question(question: str) -> tuple[str, frozenset[str]]:
    """Normalize surface form while retaining business-significant modifiers."""
    lowered = question.lower().replace("_", " ")
    raw_tokens = re.findall(r"[a-z0-9]+", lowered)
    normalized = " ".join(raw_tokens)
    tokens = [SINGULAR_FORMS.get(token, token) for token in raw_tokens]
    features = set(tokens)
    if "count" in features or "number" in features or "how many" in normalized:
        features.add(COUNT_INTENT)
    if "net of" in normalized:
        features.add(NET_OF)
    return normalized, frozenset(features)


def _contains_form(question: str, normalized: str, form: str) -> bool:
    if "_" in form:
        return re.search(
            rf"(?<![a-z0-9_]){re.escape(form.lower())}(?![a-z0-9_])",
            question.lower(),
        ) is not None
    normalized_form, _ = _normalize_question(form)
    return f" {normalized_form} " in f" {normalized} "


def _rule_matches(rule: CompositionPattern, features: frozenset[str]) -> bool:
    return all(features.intersection(group) for group in rule.required_feature_groups)


def _metric_candidates(question: str) -> list[str]:
    normalized, features = _normalize_question(question)
    candidates = set()

    for definition in METRIC_DEFINITIONS:
        metadata = definition.resolver
        if any(alias in question for alias in metadata.cjk_aliases) or any(
            _contains_form(question, normalized, form)
            for form in metadata.canonical_forms + metadata.aliases
        ):
            candidates.add(definition.metric_id)

        if any(
            _rule_matches(pattern, features)
            for pattern in metadata.composition_patterns
        ):
            candidates.add(definition.metric_id)

    return [
        definition.metric_id
        for definition in METRIC_DEFINITIONS
        if definition.metric_id in candidates
    ]


def _guard_reason(question: str) -> str | None:
    _, features = _normalize_question(question)
    for rule in GUARD_RULES:
        if not rule.all_features.issubset(features):
            continue
        if rule.any_features and not rule.any_features.intersection(features):
            continue
        return rule.reason
    return None


def _filters(question: str) -> dict[str, str]:
    filters = {}
    for pattern in REGION_PATTERNS:
        match = pattern.search(question)
        if match:
            filters["region"] = match.group(1).lower()
            break
    for pattern in STATUS_PATTERNS:
        match = pattern.search(question)
        if match:
            filters["status"] = match.group(1).lower()
            break
    return filters


def _scope_is_ambiguous(question: str) -> bool:
    return any(marker in question for marker in UNSPECIFIED_SCOPE_MARKERS)


def build_semantic_plan(question: str) -> SemanticPlan:
    """Resolve only semantics that the current deterministic runtime can execute."""
    candidates = _metric_candidates(question)
    filters = _filters(question)
    guard_reason = _guard_reason(question)

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
    if _scope_is_ambiguous(question):
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


def resolve_metric(question: str):
    """Backward-compatible metric view of an executable semantic plan."""
    plan = build_semantic_plan(question)
    return plan.metric if plan.status == PLAN_READY else None
