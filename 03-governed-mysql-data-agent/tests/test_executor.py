from decimal import Decimal

import pytest

from src.agent import DataAgent
from src.compiler import CompiledQuery
from src.executor import (
    ExecutionError,
    MySQLConfig,
    MySQLExecutor,
    SQLiteExecutor,
    executor_from_env,
)


class FakeCursor:
    column_names = ("revenue",)

    def __init__(self):
        self.executed = None
        self.closed = False
        self.rows = [(Decimal("180.00"),)]

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.prepared = None
        self.closed = False

    def cursor(self, *, prepared):
        self.prepared = prepared
        return self.cursor_instance

    def close(self):
        self.closed = True


class FakeConnector:
    def __init__(self):
        self.connection = FakeConnection()
        self.connect_kwargs = None

    def connect(self, **kwargs):
        self.connect_kwargs = kwargs
        return self.connection


def _mysql_config():
    return MySQLConfig(
        host="mysql.test",
        port=3307,
        database="data_agent",
        user="agent_ro",
        password="test-only",
    )


def test_sqlite_executor_runs_compiled_query_with_bound_params(tmp_path):
    executor = SQLiteExecutor(tmp_path / "demo.db")
    query = CompiledQuery(
        sql="SELECT ? AS value", result_metric="value", params=(7,)
    )

    assert executor.execute(query) == {"value": 7}


def test_sqlite_executor_rejects_zero_rows_for_scalar_contract(tmp_path):
    executor = SQLiteExecutor(tmp_path / "demo.db")
    query = CompiledQuery(
        sql="SELECT 1 AS value WHERE 0",
        result_metric="value",
    )

    with pytest.raises(ExecutionError, match="got zero"):
        executor.execute(query)


def test_mysql_executor_uses_native_prepared_query_and_bound_params():
    connector = FakeConnector()
    executor = MySQLExecutor(_mysql_config(), connector_module=connector)
    query = CompiledQuery(
        sql="SELECT ? + ? AS revenue",
        result_metric="revenue",
        params=(Decimal("200.00"), Decimal("-20.00")),
    )

    evidence = executor.execute(query)

    assert connector.connection.prepared is True
    assert connector.connection.cursor_instance.executed == (
        query.sql,
        query.params,
    )
    assert connector.connect_kwargs == {
        "host": "mysql.test",
        "port": 3307,
        "database": "data_agent",
        "user": "agent_ro",
        "password": "test-only",
    }
    assert evidence == {"revenue": 180.0}
    assert connector.connection.cursor_instance.closed is True
    assert connector.connection.closed is True


def test_mysql_executor_rejects_multiple_rows_for_scalar_contract():
    connector = FakeConnector()
    connector.connection.cursor_instance.rows.append((Decimal("20.00"),))
    executor = MySQLExecutor(_mysql_config(), connector_module=connector)
    query = CompiledQuery(
        sql="SELECT amount AS revenue FROM payments",
        result_metric="revenue",
    )

    with pytest.raises(ExecutionError, match="more than one"):
        executor.execute(query)

    assert connector.connection.cursor_instance.closed is True
    assert connector.connection.closed is True


def test_mysql_configuration_requires_environment_values():
    with pytest.raises(ExecutionError, match="MYSQL_AGENT_PASSWORD"):
        MySQLConfig.from_env(
            {
                "MYSQL_HOST": "127.0.0.1",
                "MYSQL_PORT": "3306",
                "MYSQL_DATABASE": "data_agent",
                "MYSQL_AGENT_USER": "agent_ro",
            }
        )


def test_explicit_mysql_selection_never_falls_back_when_config_is_missing():
    with pytest.raises(ExecutionError, match="MYSQL_HOST"):
        executor_from_env(
            environment={
                "DATA_AGENT_EXECUTOR": "mysql",
                "MYSQL_PORT": "3306",
                "MYSQL_DATABASE": "data_agent",
                "MYSQL_AGENT_USER": "agent_ro",
                "MYSQL_AGENT_PASSWORD": "test-only",
            }
        )


def test_executor_selection_defaults_to_sqlite_and_requires_known_backend(tmp_path):
    default = executor_from_env(tmp_path / "demo.db", {})

    assert isinstance(default, SQLiteExecutor)
    with pytest.raises(ExecutionError, match="unsupported DATA_AGENT_EXECUTOR"):
        executor_from_env(environment={"DATA_AGENT_EXECUTOR": "oracle"})


def test_mysql_runtime_rejects_root_or_shared_admin_identity():
    common = {
        "MYSQL_HOST": "127.0.0.1",
        "MYSQL_PORT": "3306",
        "MYSQL_DATABASE": "data_agent",
        "MYSQL_AGENT_PASSWORD": "test-only",
    }

    with pytest.raises(ExecutionError, match="admin/root"):
        MySQLConfig.from_env({**common, "MYSQL_AGENT_USER": "root"})
    with pytest.raises(ExecutionError, match="admin/root"):
        MySQLConfig.from_env(
            {
                **common,
                "MYSQL_ADMIN_USER": "setup_admin",
                "MYSQL_AGENT_USER": "setup_admin",
            }
        )


def test_mysql_connection_failure_is_explicit_and_not_a_fake_success():
    class FailingConnector:
        @staticmethod
        def connect(**kwargs):
            raise OSError("connection refused")

    executor = MySQLExecutor(
        _mysql_config(), connector_module=FailingConnector()
    )
    agent = DataAgent(executor=executor)

    result = agent.answer("revenue")

    assert result["status"] == "ERROR"
    assert result["executor"] == "mysql"
    assert "connection refused" in result["reason"]
    assert result["trace"] == [
        "resolve_metric",
        "compile_query",
        "validate_sql",
        "execute_sql",
    ]
    assert "evidence" not in result
    assert "verified" not in result


def test_mysql_query_failure_is_explicit_and_not_a_fake_success():
    class FailingQueryCursor(FakeCursor):
        def execute(self, sql, params):
            raise RuntimeError("query execution rejected")

    class FailingQueryConnection(FakeConnection):
        def __init__(self):
            super().__init__()
            self.cursor_instance = FailingQueryCursor()

    class FailingQueryConnector:
        def __init__(self):
            self.connection = FailingQueryConnection()

        def connect(self, **kwargs):
            return self.connection

    connector = FailingQueryConnector()
    agent = DataAgent(
        executor=MySQLExecutor(_mysql_config(), connector_module=connector)
    )

    result = agent.answer("revenue")

    assert result["status"] == "ERROR"
    assert result["executor"] == "mysql"
    assert "query execution rejected" in result["reason"]
    assert "evidence" not in result
    assert "verified" not in result
    assert connector.connection.cursor_instance.closed is True
    assert connector.connection.closed is True
