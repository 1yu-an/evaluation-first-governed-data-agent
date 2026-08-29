import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError


PARSE_FAILURE = "parse failure / SQL 解析失败"
MULTIPLE_STATEMENTS = "multiple statements / 禁止多语句"
WRITE_STATEMENT = "write statement / 禁止写操作"
UNSUPPORTED_STATEMENT = "unsupported statement type / 不支持的语句类型"

WRITE_EXPRESSION_TYPES = (
    exp.DML,
    exp.Alter,
    exp.Create,
    exp.Drop,
    exp.TruncateTable,
)
NON_READ_ONLY_QUERY_TYPES = (exp.Into, exp.Lock)


def validate_sql(sql: str) -> tuple[bool, str]:
    """Allow one parsed, read-only SELECT query and fail closed otherwise."""
    if not isinstance(sql, str) or not sql.strip():
        return False, PARSE_FAILURE

    try:
        statements = sqlglot.parse(
            sql,
            read="mysql",
            error_level=sqlglot.ErrorLevel.RAISE,
        )
    except (SqlglotError, TypeError, ValueError):
        return False, PARSE_FAILURE

    if len(statements) != 1:
        return False, MULTIPLE_STATEMENTS

    statement = statements[0]
    if statement is None:
        return False, PARSE_FAILURE

    if any(
        isinstance(node, WRITE_EXPRESSION_TYPES)
        for node in statement.walk()
    ):
        return False, WRITE_STATEMENT

    if not isinstance(statement, exp.Query) or statement.find(exp.Select) is None:
        return False, UNSUPPORTED_STATEMENT

    if any(
        isinstance(node, NON_READ_ONLY_QUERY_TYPES)
        for node in statement.walk()
    ):
        return False, UNSUPPORTED_STATEMENT

    return True, "ok"


def evaluate_sql_policy(sql: str) -> dict:
    """Return the real policy decision in a structured public result."""
    allowed, reason = validate_sql(sql)
    return {
        "allowed": allowed,
        "reason": reason,
        "trace": ["validate_sql"],
    }
