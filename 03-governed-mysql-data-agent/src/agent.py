from .compiler import CompileError, compile_plan
from .executor import ExecutionError, QueryExecutor, SQLiteExecutor
from .semantic import METRICS, PLAN_READY, build_semantic_plan
from .policy import validate_sql


def _verify_metric_evidence(metric: str, evidence: dict) -> dict:
    passed = metric in evidence and evidence[metric] is not None
    return {
        "method": "metric_key_present_and_non_null",
        "passed": passed,
    }


class DataAgent:
    def __init__(
        self,
        db_path="demo.db",
        *,
        executor: QueryExecutor | None = None,
    ):
        self.db_path = db_path
        self.executor = executor or SQLiteExecutor(db_path)

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
        try:
            evidence = self.executor.execute(compiled)
        except ExecutionError as error:
            return {
                "status": "ERROR",
                "reason": str(error),
                "semantic_plan": plan.to_dict(),
                "sql": sql,
                "params": list(compiled.params),
                "policy_allowed": True,
                "policy_reason": reason,
                "executor": self.executor.name,
                "trace": trace,
            }
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
            "executor": self.executor.name,
            "policy_allowed": True,
            "policy_reason": reason,
            "verification": verification,
            "verified": verification["passed"],
            "trace": trace,
        }
