import re

FORBIDDEN = re.compile(r"\b(delete|drop|truncate|alter|update|insert|replace|grant|revoke)\b", re.I)

def validate_sql(sql: str) -> tuple[bool,str]:
    cleaned=sql.strip()
    if not cleaned.lower().startswith("select"):
        return False,"only SELECT is allowed / 仅允许 SELECT"
    if FORBIDDEN.search(cleaned):
        return False,"destructive keyword blocked / 已拦截破坏性关键字"
    if ";" in cleaned[:-1]:
        return False,"multiple statements blocked / 禁止多语句"
    return True,"ok"
