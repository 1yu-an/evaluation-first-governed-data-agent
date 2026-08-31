"""Validate a Domain Profile against an observed database schema."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .profile import DomainProfile, required_schema


MYSQL_SCHEMA_QUERY = (
    "SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
    "WHERE TABLE_SCHEMA = %s"
)


class SchemaValidationError(RuntimeError):
    """The selected profile references missing database objects."""

    def __init__(
        self,
        missing_tables: Iterable[str] = (),
        missing_columns: Iterable[str] = (),
    ):
        self.missing_tables = tuple(sorted(missing_tables))
        self.missing_columns = tuple(sorted(missing_columns))
        details = [f"missing table {name}" for name in self.missing_tables]
        details += [f"missing column {name}" for name in self.missing_columns]
        super().__init__("SCHEMA_MISMATCH: " + "; ".join(details))


class SchemaInspectionError(RuntimeError):
    """MySQL metadata could not be read safely."""


def validate_schema_snapshot(
    profile: DomainProfile,
    snapshot: Mapping[str, Iterable[str]],
) -> None:
    observed = {table: set(columns) for table, columns in snapshot.items()}
    missing_tables = []
    missing_columns = []
    for table, columns in required_schema(profile).items():
        if table not in observed:
            missing_tables.append(table)
            continue
        missing_columns.extend(
            f"{table}.{column}"
            for column in sorted(columns - observed[table])
        )
    if missing_tables or missing_columns:
        raise SchemaValidationError(missing_tables, missing_columns)


def fetch_mysql_schema(
    connection: Any, database: str
) -> dict[str, frozenset[str]]:
    cursor = connection.cursor()
    try:
        cursor.execute(MYSQL_SCHEMA_QUERY, (database,))
        rows = cursor.fetchall()
    finally:
        cursor.close()
    snapshot: dict[str, set[str]] = {}
    for table, column in rows:
        snapshot.setdefault(str(table), set()).add(str(column))
    return {
        table: frozenset(columns)
        for table, columns in snapshot.items()
    }


def validate_mysql_schema(
    profile: DomainProfile, connection: Any, database: str
) -> None:
    validate_schema_snapshot(
        profile, fetch_mysql_schema(connection, database)
    )


def validate_mysql_config_schema(
    profile: DomainProfile,
    config: Any,
    connector_module: Any,
) -> None:
    connection = None
    try:
        connection = connector_module.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.user,
            password=config.password,
        )
        validate_mysql_schema(profile, connection, config.database)
    except SchemaValidationError:
        raise
    except Exception as error:
        raise SchemaInspectionError(
            f"MySQL schema inspection failed: {error}"
        ) from error
    finally:
        if connection is not None:
            connection.close()
