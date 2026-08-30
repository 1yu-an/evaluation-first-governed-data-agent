import os
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from .compiler import CompiledQuery


class ExecutionError(RuntimeError):
    """Raised when a database executor cannot return query evidence."""


class QueryExecutor(Protocol):
    name: str

    def execute(self, query: CompiledQuery) -> dict[str, Any]: ...


class SQLiteExecutor:
    name = "sqlite"

    def __init__(self, db_path: str | Path):
        self.db_path = db_path

    def execute(self, query: CompiledQuery) -> dict[str, Any]:
        try:
            with closing(sqlite3.connect(self.db_path)) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(query.sql, query.params).fetchone()
        except sqlite3.Error as error:
            raise ExecutionError(
                f"SQLite execution failed / SQLite 执行失败: {error}"
            ) from error
        return dict(row) if row is not None else {}


def _required_environment(
    environment: Mapping[str, str], name: str
) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ExecutionError(
            f"missing required environment variable: {name} / 缺少必要环境变量"
        )
    return value


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(
        cls, environment: Mapping[str, str] | None = None
    ) -> "MySQLConfig":
        values = os.environ if environment is None else environment
        port_text = _required_environment(values, "MYSQL_PORT")
        try:
            port = int(port_text)
        except ValueError as error:
            raise ExecutionError(
                "MYSQL_PORT must be an integer / MYSQL_PORT 必须是整数"
            ) from error
        if not 1 <= port <= 65535:
            raise ExecutionError(
                "MYSQL_PORT is outside 1..65535 / MYSQL_PORT 超出有效范围"
            )
        user = _required_environment(values, "MYSQL_AGENT_USER")
        admin_user = values.get("MYSQL_ADMIN_USER", "").strip()
        if user.lower() == "root" or (admin_user and user == admin_user):
            raise ExecutionError(
                "MYSQL_AGENT_USER must be distinct from the admin/root account / "
                "MySQL 运行账号必须与管理员账号分离"
            )
        return cls(
            host=_required_environment(values, "MYSQL_HOST"),
            port=port,
            database=_required_environment(values, "MYSQL_DATABASE"),
            user=user,
            password=_required_environment(values, "MYSQL_AGENT_PASSWORD"),
        )


def _load_mysql_connector():
    try:
        import mysql.connector
    except ImportError as error:
        raise ExecutionError(
            "mysql-connector-python is required for MySQL execution / "
            "MySQL 执行需要 mysql-connector-python"
        ) from error
    return mysql.connector


def _evidence_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


class MySQLExecutor:
    name = "mysql"

    def __init__(
        self,
        config: MySQLConfig,
        connector_module: Any | None = None,
    ):
        self.config = config
        self._connector_module = connector_module

    @classmethod
    def from_env(cls) -> "MySQLExecutor":
        return cls(MySQLConfig.from_env())

    def execute(self, query: CompiledQuery) -> dict[str, Any]:
        connector = self._connector_module or _load_mysql_connector()
        connection = None
        cursor = None
        try:
            connection = connector.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
            )
            # Connector/Python prepared cursors accept native ``?`` markers.
            # The compiler SQL and its params therefore remain separate and
            # unchanged for both SQLite and MySQL.
            cursor = connection.cursor(prepared=True)
            cursor.execute(query.sql, query.params)
            row = cursor.fetchone()
            if row is None:
                return {}
            return {
                name: _evidence_value(value)
                for name, value in zip(cursor.column_names, row)
            }
        except ExecutionError:
            raise
        except Exception as error:
            raise ExecutionError(
                f"MySQL execution failed / MySQL 执行失败: {error}"
            ) from error
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()


def executor_from_env(
    db_path: str | Path = "demo.db",
    environment: Mapping[str, str] | None = None,
) -> QueryExecutor:
    values = os.environ if environment is None else environment
    backend = values.get("DATA_AGENT_EXECUTOR", "sqlite").strip().lower()
    if backend == "sqlite":
        return SQLiteExecutor(db_path)
    if backend == "mysql":
        return MySQLExecutor(MySQLConfig.from_env(values))
    raise ExecutionError(
        f"unsupported DATA_AGENT_EXECUTOR: {backend} / 不支持的数据库执行器"
    )
