# Five-minute Web Interview Demo / 五分钟网页二面演示

## Before the interview / 面试前

From the repository root, activate the prepared Python 3.12+ environment and run:

```powershell
python scripts\run_web_demo.py
```

Open `http://127.0.0.1:8000`. The default deterministic SQLite database is created
automatically when missing.

## 0:00–0:30 — Problem and boundary / 问题与边界

This is not open-ended Text-to-SQL. It accepts only governed business semantics,
compiles deterministic SQL, applies an AST read-only policy, executes through a
restricted executor, and verifies the returned evidence. Ambiguity fails closed.

## 0:30–1:30 — Successful query / 正常查询

Run `highest completed order total`. Point out `OK`, metric
`max_completed_order_total`, evidence `120.0`, `verified=true`, and the complete
five-stage trace.

## 1:30–2:30 — Plan, parameters, and trace / 计划、参数与轨迹

Run `revenue for the east region`. Show that the real SemanticPlan retains the
`east` filter and that SQL structure is separate from bound params. Follow the
actual Resolver → Compiler → AST Policy → Executor → Verification trace.

## 2:30–3:30 — Fail closed / 安全失败

Run `turnover`. Explain why the governed resolver refuses to guess its business
meaning. Only Resolver executed; Compiler, Policy, Database, and Verification are
correctly shown as `Not Executed`. Optionally repeat with
`show me customer email addresses` to show the approved semantic boundary.

## 3:30–4:15 — Defense in depth / 纵深防御

Explain that deterministic compilation separates values from SQL structure, the
AST Policy allows only one read-only SELECT/CTE, and MySQL production-path evidence
uses a distinct SELECT-only runtime identity. The Web layer has no raw-SQL endpoint.

## 4:15–5:00 — Evaluation evidence / 评测证据

Show `53 / 56`, `SAFE_FAILURE=3`, `FALSE_SUCCESS=0`, `UNSAFE_ALLOW=0`, and
`OVER_BLOCK=0`. The three remaining ambiguous phrases are intentional safe failures,
so 53/56 is the declared governed result—not an unfinished attempt at 56/56.
