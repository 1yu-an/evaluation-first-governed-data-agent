import re

FORBIDDEN = re.compile(r"\b(delete|drop|truncate|alter|update|insert|replace|grant|revoke)\b", re.I)


def validate_sql(sql: str) -> tuple[bool, str]:
    cleaned = sql.strip()
    if not cleaned.lower().startswith("select"):
        return False, "only SELECT is allowed / 仅允许 SELECT"
    if FORBIDDEN.search(cleaned):
        return False, "destructive keyword blocked / 已拦截破坏性关键字"
    if ";" in cleaned[:-1]:
        return False, "multiple statements blocked / 禁止多语句"
    return True, "ok"


def evaluate_sql_policy(sql: str) -> dict:
    """Return the real policy decision in a structured public result."""
    allowed, reason = validate_sql(sql)
    return {
        "allowed": allowed,
        "reason": reason,
        "trace": ["validate_sql"],
    }
