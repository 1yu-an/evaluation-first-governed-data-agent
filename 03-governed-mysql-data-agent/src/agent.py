import sqlite3
from contextlib import closing

from .compiler import CompileError, compile_plan
from .semantic import METRICS, PLAN_READY, build_semantic_plan
from .policy import validate_sql


def _verify_metric_evidence(metric: str, evidence: dict) -> dict:
    passed = metric in evidence and evidence[metric] is not None
    return {
        "method": "metric_key_present_and_non_null",
        "passed": passed,
    }


class DataAgent:
    def __init__(self, db_path="demo.db"):
        self.db_path = db_path

    def answer(self, question: str) -> dict:
        trace = ["resolve_metric"]
        plan = build_semantic_plan(question)
        if plan.status != PLAN_READY:
            return {
                "status": "NEED_CLARIFICATION",
                "reason": plan.reason,
                "semantic_plan": plan.to_dict(),
                "trace": trace,
            }

        metric = plan.metric
        trace.append("compile_query")
        try:
            compiled = compile_plan(plan)
        except CompileError as error:
            return {
                "status": "NEED_CLARIFICATION",
                "reason": str(error),
                "semantic_plan": plan.to_dict(),
                "trace": trace,
            }

        sql = compiled.sql
        trace.append("validate_sql")
        ok, reason = validate_sql(sql)
        if not ok:
            return {
                "status": "BLOCKED",
                "reason": reason,
                "sql": sql,
                "policy_allowed": False,
                "policy_reason": reason,
                "trace": trace,
            }

        trace.append("execute_sql")
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, compiled.params).fetchone()
        evidence = dict(row) if row is not None else {}
        if compiled.result_metric != metric and metric in evidence:
            evidence = {compiled.result_metric: evidence[metric]}
        verification = _verify_metric_evidence(compiled.result_metric, evidence)
        trace.append("verify_evidence")
        return {
            "status": "OK",
            "metric": compiled.result_metric,
            "semantic_plan": plan.to_dict(),
            "definition": METRICS[metric]["description"],
            "sql": sql,
            "params": list(compiled.params),
            "evidence": evidence,
            "policy_allowed": True,
            "policy_reason": reason,
            "verification": verification,
            "verified": verification["passed"],
            "trace": trace,
        }
