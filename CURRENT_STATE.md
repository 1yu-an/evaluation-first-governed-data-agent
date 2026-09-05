# Current Repository State

Verified on: 2026-08-31 (Asia/Shanghai)
Frozen feature commit: `68795ef10b5c54a999eae3cc2e956595030cf1df`
Evidence closure commit: `67986697a55537f4ebc463425c886fa65228c5d2`
Hosted evidence: [CI Regression Gate run 33362031707](https://github.com/1yu-an/evaluation-first-governed-data-agent/actions/runs/33362031707)

This file is a concise status snapshot, not a second project README. The
reviewer-facing source of truth for project 03 is
[`03-governed-mysql-data-agent/README.md`](03-governed-mysql-data-agent/README.md).

## Feature status

Project 03 feature development is frozen. The current scope is an
evaluation-first governed data-agent prototype with deterministic semantics,
fail-closed behavior, AST SQL policy, least-privilege execution, strict result
contracts, and a fixed external Benchmark.

Core Agent remains frozen. A thin same-origin FastAPI and local HTML/CSS/JavaScript
presentation layer has been added for reproducible Windows interview demonstration.
It delegates questions to the existing `DataAgent` and does not own semantic
resolution, SQL compilation, policy, database access, or verification.

## Final architecture

```text
Question
→ Governed Resolver
→ SemanticPlan
→ Metric Catalog
→ Deterministic Compiler
→ AST SQL Policy
→ QueryExecutor
→ SQLite / MySQL
→ Database Least Privilege
→ Strict Result Verification
→ Eval / Benchmark / Regression Gate
```

## Verified results

- Project 03 ordinary suite: `172 passed, 1 skipped, 13 subtests passed`.
- Project 00 suite: `59 passed`.
- Repository structure/source validation: passed.
- Repository audit tests: `17 passed`; deterministic audit: `PASS` with zero
  findings.
- Project 01: `3` Maven tests, including a Spring Boot 4.0.8 context startup.
- Project 06: `2` Maven tests, including a Spring Boot 4.0.8 context startup.
- Fixed 56-case system Benchmark: `53 / 56` success.
- Dimension results: outcome/conformance/state/policy/overall `0.946429`;
  verification `21 / 24 = 0.875000`.
- Safety classification: `SAFE_FAILURE=3`, `FALSE_SUCCESS=0`,
  `UNSAFE_ALLOW=0`, `OVER_BLOCK=0`.
- The standalone Benchmark gate hard-fails on any `FALSE_SUCCESS` or
  `UNSAFE_ALLOW`, independently of aggregate score thresholds.
- Fixed Eval Set SHA-256:
  `FFA2D213867C1AD80F386EE2D762FD91224C215E23F91FC4A6B0A2F66675A40E`.

## MySQL safety evidence

The hosted workflow provisioned disposable MySQL `8.0.46` and passed the real
integration suite `8 / 8` on the evidence closure commit. `setup_mysql.py` ran
as the admin/setup identity; the distinct `data_agent_ro` runtime account had
only `USAGE` plus `SELECT` on its target database. Direct UPDATE, INSERT, and
DELETE attempts were rejected by MySQL independently of the application AST
Policy. SQLite and MySQL evidence matched for all governed queries in the
parity test.

Local MySQL remains opt-in; hosted CI runs it without repository secrets. The
default demo and fixed Benchmark continue to use deterministic SQLite.

## Remaining SAFE_FAILURE cases

The final three cases intentionally return `NEED_CLARIFICATION` after Resolver
only and emit no SQL or business value:

- `money made`
- `turnover`
- `fulfilled purchases`

They are retained because their business meanings are ambiguous; 53/56 is the
declared final governed result, not an unfinished target on the way to 56/56.

## Important commits

| Commit | Change |
|---|---|
| `e2e26c9` | establish frozen 56-case Baseline v0 (37/56) |
| `3fa52d2` | add SemanticPlan safety gate |
| `e2e94d7` | replace regex SQL policy with AST validation |
| `5c66e81` | add filter-aware deterministic SQL compiler |
| `b4a38df` | add read-only MySQL execution boundary |
| `285ff21` | add strict result verification contract |
| `d6aafea` | add governed metric lexicon resolver |
| `f2a1392` | add governed metric catalog and payment metrics |
| `07e8fdb` | add governed pending-orders metric |
| `68795ef` | add governed maximum completed-order metric; freeze features |

## Freeze declaration

Do not add metrics, broaden ambiguous resolver mappings, modify the fixed Eval
Set, or pursue 56/56 as packaging work. Subsequent changes should be limited to
delivery documentation, dependency closure, reproducibility, or corrections to
evidence about the frozen implementation.
