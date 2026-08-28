import sqlite3
from .semantic import METRICS, resolve_metric
from .policy import validate_sql

class DataAgent:
    def __init__(self, db_path="demo.db"): self.db_path=db_path

    def answer(self, question: str) -> dict:
        metric=resolve_metric(question)
        if not metric:
            return {"status":"NEED_CLARIFICATION","reason":"unknown business metric / 未知业务指标"}
        sql=METRICS[metric]["sql"]
        ok,reason=validate_sql(sql)
        if not ok: return {"status":"BLOCKED","reason":reason,"sql":sql}
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory=sqlite3.Row
            row=conn.execute(sql).fetchone()
        return {"status":"OK","metric":metric,"definition":METRICS[metric]["description"],"sql":sql,"evidence":dict(row),"verified":True}
