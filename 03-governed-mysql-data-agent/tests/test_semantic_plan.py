import pytest

from src.agent import DataAgent
from src.catalog import METRIC_CATALOG, METRIC_DEFINITIONS
from src.demo import initialize_demo
from src.semantic import (
    PLAN_NEEDS_CLARIFICATION,
    PLAN_READY,
    build_semantic_plan,
)


def test_canonical_revenue_plan_remains_executable():
    plan = build_semantic_plan("Please show the revenue metric")

    assert plan.status == PLAN_READY
    assert plan.metric == "revenue"
    assert plan.filters == {}


def test_configured_explicit_chinese_alias_remains_executable():
    plan = build_semantic_plan("请查询收入")

    assert plan.status == PLAN_READY
    assert plan.metric == "revenue"


def test_multiple_metrics_require_clarification():
    plan = build_semantic_plan("revenue or completed_orders")

    assert plan.status == PLAN_NEEDS_CLARIFICATION
    assert plan.metric is None
    assert "multiple business metrics" in plan.reason


def test_vague_scope_marker_requires_clarification_without_rejecting_all_short_inputs():
    vague = build_semantic_plan("查一下收入")
    explicit = build_semantic_plan("收入")

    assert vague.status == PLAN_NEEDS_CLARIFICATION
    assert vague.metric == "revenue"
    assert explicit.status == PLAN_READY
    assert explicit.metric == "revenue"


def test_supported_region_filter_is_preserved_compiled_and_executed(tmp_path):
    db_path = initialize_demo(tmp_path / "demo.db")

    result = DataAgent(db_path).answer("revenue for the north region")

    assert result["status"] == "OK"
    assert result["semantic_plan"]["metric"] == "revenue"
    assert result["semantic_plan"]["filters"] == {"region": "north"}
    assert result["params"] == ["north", "north"]
    assert "north" not in result["sql"]
    assert result["metric"] == "north_revenue"
    assert result["evidence"] == {"north_revenue": 0.0}
    assert result["verified"] is True


@pytest.mark.parametrize(
    ("region", "expected"),
    [("south", 0.0), ("east", 100.0)],
)
def test_region_revenue_compilation_generalizes_beyond_benchmark_case(
    region, expected, tmp_path
):
    db_path = initialize_demo(tmp_path / f"{region}.db")

    result = DataAgent(db_path).answer(f"revenue for the {region} region")

    result_metric = f"{region}_revenue"
    assert result["status"] == "OK"
    assert result["metric"] == result_metric
    assert result["evidence"] == {result_metric: expected}
    assert result["params"] == [region, region]


@pytest.mark.parametrize(
    "question",
    [
        "查一下收入",
        "收入还是订单数",
        "revenue or completed_orders",
    ],
)
def test_original_false_success_regressions_stop_before_sql(question, tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer(question)

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["trace"] == ["resolve_metric"]
    assert "evidence" not in result
    assert "verified" not in result
    assert not db_path.exists()


@pytest.mark.parametrize(
    "question",
    [
        "How much money did we make?",
        "What is our turnover?",
        "Count fulfilled purchases",
    ],
)
def test_deliberately_rejected_synonyms_do_not_execute_sql(question, tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer(question)

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["trace"] == ["resolve_metric"]
    assert "verified" not in result
    assert not db_path.exists()


@pytest.mark.parametrize(
    ("question", "metric"),
    [
        ("finished order count", "completed_orders"),
        ("How many orders were completed?", "completed_orders"),
        ("What is the average basket value?", "avg_order_value"),
        ("mean completed order amount", "avg_order_value"),
        ("Show net sales after refunds", "revenue"),
        ("net revenue", "revenue"),
        ("completed order count", "completed_orders"),
        ("pending order count", "pending_orders"),
        ("number of pending orders", "pending_orders"),
        ("how many orders are pending", "pending_orders"),
        ("aov", "avg_order_value"),
    ],
)
def test_governed_low_ambiguity_paraphrases_resolve(question, metric):
    plan = build_semantic_plan(question)

    assert plan.status == PLAN_READY
    assert plan.metric == metric


def test_net_sales_after_refunds_uses_existing_revenue_definition(tmp_path):
    db_path = initialize_demo(tmp_path / "net-sales.db")

    result = DataAgent(db_path).answer("Show net sales after refunds")

    assert result["status"] == "OK"
    assert result["metric"] == "revenue"
    assert result["definition"] == METRIC_CATALOG["revenue"].business_meaning
    assert result["evidence"] == {"revenue": 180.0}
    assert "payments" in result["sql"]
    assert "refunds" in result["sql"]


@pytest.mark.parametrize(
    "question",
    [
        "revenue growth rate",
        "employee turnover",
        "inventory turnover",
        "stock turnover",
        "turnover rate",
        "average basket size",
        "customer lifetime value",
        "net sales before refunds",
        "not revenue",
    ],
)
def test_unknown_or_unsupported_expressions_fail_closed(question):
    plan = build_semantic_plan(question)

    assert plan.status == PLAN_NEEDS_CLARIFICATION
    assert plan.metric is None


def test_paraphrase_candidates_for_two_metrics_require_clarification():
    plan = build_semantic_plan(
        "Compare average basket value with finished order count"
    )

    assert plan.status == PLAN_NEEDS_CLARIFICATION
    assert plan.metric is None
    assert "multiple business metrics" in plan.reason


def test_per_unit_expression_does_not_collapse_to_revenue():
    plan = build_semantic_plan("money made per order")

    assert plan.status == PLAN_NEEDS_CLARIFICATION
    assert plan.metric is None
    assert "per-unit" in plan.reason


@pytest.mark.parametrize(
    ("question", "metric"),
    [
        ("revenue", "revenue"),
        ("completed_orders", "completed_orders"),
        ("avg_order_value", "avg_order_value"),
        ("completed orders", "completed_orders"),
        ("average order value", "avg_order_value"),
        ("收入", "revenue"),
        ("营收", "revenue"),
        ("订单数", "completed_orders"),
        ("客单价", "avg_order_value"),
        ("pending_orders", "pending_orders"),
        ("pending orders", "pending_orders"),
    ],
)
def test_canonical_forms_and_existing_aliases_do_not_regress(question, metric):
    plan = build_semantic_plan(question)

    assert plan.status == PLAN_READY
    assert plan.metric == metric


@pytest.mark.parametrize(
    ("question", "metric", "evidence"),
    [
        (
            "total number of finished orders",
            "completed_orders",
            {"completed_orders": 2},
        ),
        (
            "number of orders that are finished",
            "completed_orders",
            {"completed_orders": 2},
        ),
        ("mean basket amount", "avg_order_value", {"avg_order_value": 100.0}),
        (
            "average completed order amount",
            "avg_order_value",
            {"avg_order_value": 100.0},
        ),
        ("sales net of completed refunds", "revenue", {"revenue": 180.0}),
        (
            "net sales following completed refunds",
            "revenue",
            {"revenue": 180.0},
        ),
        (
            "sum of completed refunds",
            "completed_refunds",
            {"completed_refunds": 20.0},
        ),
        (
            "completed refund amount",
            "completed_refunds",
            {"completed_refunds": 20.0},
        ),
        (
            "total amount of completed payments",
            "completed_payments",
            {"completed_payments": 200.0},
        ),
        (
            "gross completed payments",
            "completed_payments",
            {"completed_payments": 200.0},
        ),
        ("pending order count", "pending_orders", {"pending_orders": 1}),
        (
            "number of pending orders",
            "pending_orders",
            {"pending_orders": 1},
        ),
        (
            "how many orders are pending",
            "pending_orders",
            {"pending_orders": 1},
        ),
    ],
)
def test_eval_set_outside_paraphrases_use_reusable_families(
    question, metric, evidence, tmp_path
):
    db_path = initialize_demo(tmp_path / "outside-eval.db")

    result = DataAgent(db_path).answer(question)

    assert result["status"] == "OK"
    assert result["metric"] == metric
    assert result["evidence"] == evidence
    assert result["verified"] is True
    assert result["trace"] == [
        "resolve_metric",
        "compile_query",
        "validate_sql",
        "execute_sql",
        "verify_evidence",
    ]


def test_resolver_uses_every_catalog_definition_without_external_metric_refs():
    assert {
        definition.metric_id for definition in METRIC_DEFINITIONS
    } == set(METRIC_CATALOG)


@pytest.mark.parametrize(
    ("question", "metric", "evidence"),
    [
        (
            "total completed refunds",
            "completed_refunds",
            {"completed_refunds": 20.0},
        ),
        (
            "gross completed payment amount",
            "completed_payments",
            {"completed_payments": 200.0},
        ),
    ],
)
def test_new_metrics_complete_the_full_governed_chain(
    question, metric, evidence, tmp_path
):
    db_path = initialize_demo(tmp_path / f"{metric}.db")

    result = DataAgent(db_path).answer(question)

    assert result["status"] == "OK"
    assert result["metric"] == metric
    assert result["evidence"] == evidence
    assert result["definition"] == METRIC_CATALOG[metric].business_meaning
    assert result["verified"] is True
    assert result["trace"] == [
        "resolve_metric",
        "compile_query",
        "validate_sql",
        "execute_sql",
        "verify_evidence",
    ]


def test_pending_orders_completes_the_full_governed_chain(tmp_path):
    db_path = initialize_demo(tmp_path / "pending-orders.db")

    result = DataAgent(db_path).answer("pending order count")

    assert result["status"] == "OK"
    assert result["semantic_plan"]["metric"] == "pending_orders"
    assert result["metric"] == "pending_orders"
    assert result["evidence"] == {"pending_orders": 1}
    assert (
        result["definition"]
        == METRIC_CATALOG["pending_orders"].business_meaning
    )
    assert result["verified"] is True
    assert result["trace"] == [
        "resolve_metric",
        "compile_query",
        "validate_sql",
        "execute_sql",
        "verify_evidence",
    ]


@pytest.mark.parametrize(
    "question",
    [
        "pending order amount",
        "pending payment count",
        "pending refund count",
        "completed pending orders",
    ],
)
def test_pending_order_negative_expressions_fail_before_sql(question, tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer(question)

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["metric"] is None
    assert result["trace"] == ["resolve_metric"]
    assert "sql" not in result
    assert "verified" not in result
    assert not db_path.exists()


@pytest.mark.parametrize(
    "question",
    [
        "pending refunds",
        "failed payments",
        "payment count",
        "refund count",
        "pending payment amount",
        "failed refund amount",
        "completed payment count",
        "completed refund count",
    ],
)
def test_payment_refund_sum_negative_expressions_fail_before_sql(
    question, tmp_path
):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer(question)

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["metric"] is None
    assert result["trace"] == ["resolve_metric"]
    assert "sql" not in result
    assert "verified" not in result
    assert not db_path.exists()


def test_unseen_multiple_metric_wording_generalizes_to_clarification():
    plan = build_semantic_plan(
        "Could you compare avg_order_value against revenue for me?"
    )

    assert plan.status == PLAN_NEEDS_CLARIFICATION
    assert plan.metric is None
    assert "multiple business metrics" in plan.reason


def test_unseen_region_and_wording_use_the_same_compiler(tmp_path):
    db_path = initialize_demo(tmp_path / "demo.db")

    result = DataAgent(db_path).answer(
        "Kindly show completed_orders for the west region"
    )

    assert result["status"] == "OK"
    assert result["semantic_plan"]["metric"] == "completed_orders"
    assert result["semantic_plan"]["filters"] == {"region": "west"}
    assert result["params"] == ["west"]
    assert result["metric"] == "west_completed_orders"
    assert result["evidence"] == {"west_completed_orders": 1}
    assert result["verified"] is True


def test_unsupported_region_is_preserved_and_stops_before_database(tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer("revenue for the central region")

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["filters"] == {"region": "central"}
    assert result["trace"] == ["resolve_metric", "compile_query"]
    assert "sql" not in result
    assert "evidence" not in result
    assert "verified" not in result
    assert not db_path.exists()


def test_explicit_status_filter_is_preserved_but_rejected_before_database(tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer("completed_orders with status pending")

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["filters"] == {"status": "pending"}
    assert result["trace"] == ["resolve_metric", "compile_query"]
    assert "sql" not in result
    assert not db_path.exists()


def test_unseen_ambiguity_wording_uses_scope_condition_not_full_sentence(tmp_path):
    db_path = tmp_path / "must-not-be-opened.db"

    result = DataAgent(db_path).answer("麻烦帮我查询一下营收数据")

    assert result["status"] == "NEED_CLARIFICATION"
    assert result["semantic_plan"]["metric"] == "revenue"
    assert result["semantic_plan"]["filters"] == {}
    assert result["trace"] == ["resolve_metric"]
    assert "verified" not in result
    assert not db_path.exists()


def test_unseen_single_metric_wording_remains_ready():
    plan = build_semantic_plan("Kindly return the completed_orders metric")

    assert plan.status == PLAN_READY
    assert plan.metric == "completed_orders"
    assert plan.filters == {}
