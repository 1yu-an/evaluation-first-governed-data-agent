import os
from datetime import date

import pytest


if os.environ.get("RUN_MYSQL_INTEGRATION") != "1":
    pytest.skip(
        "set RUN_MYSQL_INTEGRATION=1 and MySQL environment variables",
        allow_module_level=True,
    )

mysql_connector = pytest.importorskip("mysql.connector")

from src.agent import DataAgent
from src.compiler import CompiledQuery
from src.demo import initialize_demo, initialize_expenses
from src.executor import (
    ExecutionError,
    MySQLConfig,
    MySQLExecutor,
    SQLiteExecutor,
)
from src.verification import ResultContract
from src.profile import load_default_profile, load_profile
from src.schema_validation import validate_mysql_schema


@pytest.fixture(scope="module")
def mysql_config():
    return MySQLConfig.from_env()


@pytest.fixture(scope="module")
def mysql_executor(mysql_config):
    return MySQLExecutor(mysql_config)


def _direct_connection(config):
    return mysql_connector.connect(
        host=config.host,
        port=config.port,
        database=config.database,
        user=config.user,
        password=config.password,
    )


@pytest.mark.parametrize(
    ("sql", "expected", "error"),
    [
        ("SELECT 7 AS value", {"value": 7}, None),
        ("SELECT 7 AS value WHERE FALSE", None, "got zero"),
        (
            "SELECT 7 AS value UNION ALL SELECT 8 AS value",
            None,
            "more than one",
        ),
    ],
)
def test_mysql_executor_enforces_scalar_cardinality(
    mysql_executor, sql, expected, error
):
    query = CompiledQuery(
        sql=sql,
        result_metric="value",
        result_contract=ResultContract.scalar_numeric("value"),
    )

    if error is None:
        assert mysql_executor.execute(query) == expected
    else:
        with pytest.raises(ExecutionError, match=error):
            mysql_executor.execute(query)


def test_read_only_user_can_select_and_has_only_usage_plus_select(mysql_config):
    connection = _direct_connection(mysql_config)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM orders")
        assert cursor.fetchone()[0] == 3
        cursor.execute("SHOW GRANTS FOR CURRENT_USER")
        grants = [str(row[0]).upper() for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()

    assert any("GRANT SELECT ON" in grant for grant in grants)
    assert not any(
        forbidden in grant
        for grant in grants
        for forbidden in ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")
    )


def test_demo_and_personal_profiles_match_real_mysql_schema(mysql_config):
    connection = _direct_connection(mysql_config)
    try:
        validate_mysql_schema(
            load_default_profile(), connection, mysql_config.database
        )
        validate_mysql_schema(
            load_profile("profiles/expenses.json"),
            connection,
            mysql_config.database,
        )
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("sql", "params"),
    [
        ("UPDATE orders SET total=? WHERE id=?", (999, 1)),
        (
            "INSERT INTO orders(id,status,total,region) VALUES(?,?,?,?)",
            (99, "completed", 1, "north"),
        ),
        ("DELETE FROM orders WHERE id=?", (1,)),
    ],
)
def test_database_itself_rejects_writes_without_policy(
    mysql_config, sql, params
):
    connection = _direct_connection(mysql_config)
    cursor = connection.cursor(prepared=True)
    try:
        with pytest.raises(mysql_connector.Error):
            cursor.execute(sql, params)
    finally:
        connection.rollback()
        cursor.close()
        connection.close()


def test_sqlite_and_mysql_return_identical_business_evidence(
    mysql_executor, tmp_path
):
    sqlite_path = initialize_demo(tmp_path / "parity.db")
    sqlite_agent = DataAgent(executor=SQLiteExecutor(sqlite_path))
    mysql_agent = DataAgent(executor=mysql_executor)

    for question in (
        "revenue",
        "completed_orders",
        "pending order count",
        "avg_order_value",
        "highest completed order total",
        "gross completed payment amount",
        "total completed refunds",
        "revenue for the north region",
    ):
        sqlite_result = sqlite_agent.answer(question)
        mysql_result = mysql_agent.answer(question)

        assert mysql_result["status"] == "OK"
        assert mysql_result["evidence"] == sqlite_result["evidence"]
        assert mysql_result["verified"] is True


def test_expenses_profile_matches_sqlite_for_three_metrics_and_filter(
    mysql_executor, tmp_path
):
    profile = load_profile("profiles/expenses.json")
    sqlite_path = initialize_expenses(tmp_path / "expenses-parity.db")
    sqlite_agent = DataAgent(
        executor=SQLiteExecutor(sqlite_path), profile=profile
    )
    mysql_agent = DataAgent(executor=mysql_executor, profile=profile)

    for question in (
        "total expenses",
        "how many expenses",
        "average expense",
        "total expenses for groceries",
    ):
        sqlite_result = sqlite_agent.answer(question)
        mysql_result = mysql_agent.answer(question)

        assert mysql_result["status"] == "OK"
        assert mysql_result["evidence"] == sqlite_result["evidence"]
        assert mysql_result["params"] == sqlite_result["params"]
        assert mysql_result["verified"] is True


def test_v3_time_grouping_and_ranking_match_sqlite(
    mysql_executor, tmp_path
):
    profile = load_profile("profiles/expenses.json")
    reference_date = date(2026, 8, 31)
    sqlite_path = initialize_expenses(tmp_path / "v3-parity.db")
    sqlite_agent = DataAgent(
        executor=SQLiteExecutor(sqlite_path),
        profile=profile,
        reference_date=reference_date,
    )
    mysql_agent = DataAgent(
        executor=mysql_executor,
        profile=profile,
        reference_date=reference_date,
    )

    for question in (
        "total expenses this month",
        "total expenses last month",
        "expense count between 2026-08-03 and 2026-08-10",
        "total expenses by category",
        "average expense by category",
        "top 2 expense categories",
        "which category has the lowest total expenses?",
        "top 2 categories by average expense",
    ):
        sqlite_result = sqlite_agent.answer(question)
        mysql_result = mysql_agent.answer(question)

        assert sqlite_result["status"] == "OK"
        assert mysql_result["status"] == "OK"
        assert mysql_result["result_type"] == sqlite_result["result_type"]
        assert mysql_result["evidence"] == sqlite_result["evidence"]
        assert mysql_result["params"] == sqlite_result["params"]
        assert mysql_result["semantic_plan"] == sqlite_result["semantic_plan"]
        assert mysql_result["verified"] is True
