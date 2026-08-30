import os

import pytest


if os.environ.get("RUN_MYSQL_INTEGRATION") != "1":
    pytest.skip(
        "set RUN_MYSQL_INTEGRATION=1 and MySQL environment variables",
        allow_module_level=True,
    )

mysql_connector = pytest.importorskip("mysql.connector")

from src.agent import DataAgent
from src.demo import initialize_demo
from src.executor import MySQLConfig, MySQLExecutor, SQLiteExecutor


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
        "avg_order_value",
        "revenue for the north region",
    ):
        sqlite_result = sqlite_agent.answer(question)
        mysql_result = mysql_agent.answer(question)

        assert mysql_result["status"] == "OK"
        assert mysql_result["evidence"] == sqlite_result["evidence"]
        assert mysql_result["verified"] is True
