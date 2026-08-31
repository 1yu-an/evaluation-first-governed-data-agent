from decimal import Decimal

from src.compiler import CompiledQuery
from src.executor import MySQLConfig, MySQLExecutor, SQLiteExecutor
from src.verification import ResultContract, verify_evidence


def _grouped_contract(*, requested_limit=None):
    return ResultContract.grouped_numeric(
        "total_expenses",
        "category",
        max_rows=100,
        requested_limit=requested_limit,
        order="metric_desc" if requested_limit else "dimension_asc",
    )


def test_sqlite_executor_returns_grouped_mapping_rows(tmp_path):
    executor = SQLiteExecutor(tmp_path / "demo.db")
    query = CompiledQuery(
        sql=(
            "SELECT 'food' AS category, 47.5 AS total_expenses "
            "UNION ALL SELECT 'housing', 900 "
            "ORDER BY category ASC LIMIT ?"
        ),
        result_metric="total_expenses",
        result_contract=_grouped_contract(),
        params=(101,),
    )

    evidence = executor.execute(query)

    assert evidence == [
        {"category": "food", "total_expenses": 47.5},
        {"category": "housing", "total_expenses": 900},
    ]
    assert verify_evidence(query.result_contract, evidence)["passed"] is True


class GroupCursor:
    column_names = ("category", "total_expenses")

    def __init__(self, rows):
        self.rows = list(rows)
        self.closed = False

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        self.closed = True


class GroupConnection:
    def __init__(self, rows):
        self.cursor_instance = GroupCursor(rows)
        self.closed = False

    def cursor(self, *, prepared):
        assert prepared is True
        return self.cursor_instance

    def close(self):
        self.closed = True


class GroupConnector:
    def __init__(self, rows):
        self.connection = GroupConnection(rows)

    def connect(self, **kwargs):
        return self.connection


def _mysql_config():
    return MySQLConfig("mysql.test", 3306, "agent", "agent_ro", "secret")


def test_mysql_executor_normalizes_grouped_decimal_rows():
    connector = GroupConnector(
        [
            ("housing", Decimal("900.00")),
            ("food", Decimal("47.50")),
        ]
    )
    query = CompiledQuery(
        sql="SELECT category, total_expenses FROM governed LIMIT ?",
        result_metric="total_expenses",
        result_contract=_grouped_contract(requested_limit=2),
        params=(2,),
    )

    evidence = MySQLExecutor(
        _mysql_config(), connector_module=connector
    ).execute(query)

    assert evidence == [
        {"category": "housing", "total_expenses": 900.0},
        {"category": "food", "total_expenses": 47.5},
    ]
    assert verify_evidence(query.result_contract, evidence)["passed"] is True
    assert connector.connection.cursor_instance.closed is True
    assert connector.connection.closed is True


def test_grouped_executor_retains_one_overflow_row_for_verification():
    connector = GroupConnector(
        [
            ("a", Decimal("4")),
            ("b", Decimal("3")),
            ("c", Decimal("2")),
            ("d", Decimal("1")),
            ("ignored", Decimal("0")),
        ]
    )
    query = CompiledQuery(
        sql="SELECT category, total_expenses FROM governed LIMIT ?",
        result_metric="total_expenses",
        result_contract=_grouped_contract(requested_limit=3),
        params=(3,),
    )

    evidence = MySQLExecutor(
        _mysql_config(), connector_module=connector
    ).execute(query)

    assert len(evidence) == 4
    decision = verify_evidence(query.result_contract, evidence)
    assert decision["passed"] is False
    assert "requested limit" in decision["reason"]
