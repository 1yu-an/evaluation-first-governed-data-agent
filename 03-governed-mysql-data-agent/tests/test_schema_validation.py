import pytest

from src.profile import load_default_profile, load_profile
from src.schema_validation import (
    MYSQL_SCHEMA_QUERY,
    SchemaValidationError,
    SchemaInspectionError,
    fetch_mysql_schema,
    validate_mysql_config_schema,
    validate_schema_snapshot,
)


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = None
        self.closed = False

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)

    def cursor(self):
        return self.cursor_instance


def test_snapshot_accepts_exact_or_superset_expenses_schema():
    profile = load_profile("profiles/expenses.json")

    validate_schema_snapshot(
        profile,
        {"expenses": {"id", "amount", "category", "merchant"}},
    )


def test_snapshot_reports_missing_tables_and_columns_together():
    profile = load_default_profile()

    with pytest.raises(SchemaValidationError) as captured:
        validate_schema_snapshot(
            profile,
            {
                "orders": {"id", "status"},
                "payments": {"order_id", "status"},
            },
        )

    error = captured.value
    assert error.missing_tables == ("refunds",)
    assert error.missing_columns == (
        "orders.region",
        "orders.total",
        "payments.amount",
    )
    assert "SCHEMA_MISMATCH" in str(error)


def test_mysql_metadata_query_is_constant_and_database_is_bound():
    connection = FakeConnection(
        [("expenses", "amount"), ("expenses", "category")]
    )

    snapshot = fetch_mysql_schema(connection, "personal_data")

    assert connection.cursor_instance.executed == (
        MYSQL_SCHEMA_QUERY,
        ("personal_data",),
    )
    assert "personal_data" not in MYSQL_SCHEMA_QUERY
    assert snapshot == {
        "expenses": frozenset({"amount", "category"})
    }
    assert connection.cursor_instance.closed is True


def test_mysql_connection_errors_are_wrapped_without_losing_reason():
    class FailingConnector:
        @staticmethod
        def connect(**kwargs):
            raise OSError("connection refused")

    class Config:
        host = "127.0.0.1"
        port = 3306
        database = "data_agent"
        user = "reader"
        password = "test-only"

    with pytest.raises(SchemaInspectionError, match="connection refused") as captured:
        validate_mysql_config_schema(
            load_default_profile(), Config(), FailingConnector()
        )

    assert captured.value.reason_code == "database_schema_inspection_failed"


@pytest.mark.parametrize(
    ("errno", "reason_code"),
    [
        (2005, "database_host_not_found"),
        (2003, "database_connection_unavailable"),
        (1045, "database_authentication_failed"),
        (1049, "database_not_found"),
        (1044, "database_permission_denied"),
        (1142, "database_permission_denied"),
    ],
)
def test_mysql_errno_has_stable_actionable_category(errno, reason_code):
    redaction_target = "-".join(("v22", "test", "secret"))

    class ConnectorError(Exception):
        def __init__(self):
            self.errno = errno
            super().__init__(f"driver detail with {redaction_target} errno={errno}")

    class FailingConnector:
        @staticmethod
        def connect(**kwargs):
            raise ConnectorError()

    class Config:
        host = "db.test"
        port = 3306
        database = "data_agent"
        user = "reader"
        password = redaction_target

    with pytest.raises(SchemaInspectionError) as captured:
        validate_mysql_config_schema(
            load_default_profile(), Config(), FailingConnector()
        )

    error = captured.value
    assert error.reason_code == reason_code
    assert error.hint
    assert redaction_target not in str(error)
    assert "***" in str(error)
