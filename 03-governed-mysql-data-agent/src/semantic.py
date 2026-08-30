import re
from dataclasses import asdict, dataclass


METRICS = {
    "revenue": {
        "description": "Completed payment amount minus completed refunds / 已完成付款减已完成退款",
    },
    "completed_orders": {
        "description": "Count of completed orders / 已完成订单数量",
    },
    "avg_order_value": {
        "description": "Average total for completed orders / 已完成订单平均客单价",
    },
}


PLAN_READY = "READY"
PLAN_NEEDS_CLARIFICATION = "NEED_CLARIFICATION"


@dataclass(frozen=True)
class MetricLexiconEntry:
    """Governed language forms for one existing metric."""

    metric: str
    canonical_forms: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    cjk_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompositionRule:
    """Match a reusable semantic family, never a complete benchmark question."""

    metric: str
    required_feature_groups: tuple[frozenset[str], ...]


@dataclass(frozen=True)
class GuardRule:
    """Stop expressions whose modifiers change or obscure metric semantics."""

    reason: str
    all_features: frozenset[str] = frozenset()
    any_features: frozenset[str] = frozenset()


METRIC_LEXICON = (
    MetricLexiconEntry(
        metric="revenue",
        canonical_forms=("revenue",),
        aliases=("net revenue",),
        cjk_aliases=("收入", "营收"),
    ),
    MetricLexiconEntry(
        metric="completed_orders",
        canonical_forms=("completed_orders", "completed orders"),
        aliases=("completed order count",),
        cjk_aliases=("订单数",),
    ),
    MetricLexiconEntry(
        metric="avg_order_value",
        canonical_forms=("avg_order_value", "average order value"),
        aliases=("aov",),
        cjk_aliases=("客单价",),
    ),
)

COUNT_INTENT = "__count_intent__"
NET_OF = "__net_of__"
COMPOSITION_RULES = (
    CompositionRule(
        metric="completed_orders",
        required_feature_groups=(
            frozenset({"completed", "finished"}),
            frozenset({"order"}),
            frozenset({COUNT_INTENT}),
        ),
    ),
    CompositionRule(
        metric="avg_order_value",
        required_feature_groups=(
            frozenset({"avg", "average", "mean"}),
            frozenset({"order", "basket"}),
            frozenset({"value", "amount"}),
        ),
    ),
    CompositionRule(
        metric="revenue",
        required_feature_groups=(
            frozenset({"net"}),
            frozenset({"sale"}),
            frozenset({"refund"}),
            frozenset({"after", "following", NET_OF}),
        ),
    ),
)

SINGULAR_FORMS = {
    "amounts": "amount",
    "baskets": "basket",
    "orders": "order",
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
)

ALIASES = {
    alias: entry.metric
    for entry in METRIC_LEXICON
    for alias in entry.cjk_aliases
}

if {entry.metric for entry in METRIC_LEXICON} != set(METRICS):
    raise RuntimeError("metric lexicon must cover exactly the governed metric catalog")

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


def _contains_form(normalized: str, form: str) -> bool:
    normalized_form, _ = _normalize_question(form)
    return f" {normalized_form} " in f" {normalized} "


def _rule_matches(rule: CompositionRule, features: frozenset[str]) -> bool:
    return all(features.intersection(group) for group in rule.required_feature_groups)


def _metric_candidates(question: str) -> list[str]:
    normalized, features = _normalize_question(question)
    candidates = set()

    for entry in METRIC_LEXICON:
        if any(alias in question for alias in entry.cjk_aliases) or any(
            _contains_form(normalized, form)
            for form in entry.canonical_forms + entry.aliases
        ):
            candidates.add(entry.metric)

    for rule in COMPOSITION_RULES:
        if _rule_matches(rule, features):
            candidates.add(rule.metric)

    return [metric for metric in METRICS if metric in candidates]


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
