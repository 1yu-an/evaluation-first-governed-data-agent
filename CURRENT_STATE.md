# Current Repository State

Verified on: 2026-08-31 (Asia/Shanghai)

Stable v1 base: `5afe98c157d416a797b473c5bbea21c87cbdfdb0`.

Implementation branch: `codex/v2-personal-use`.

V2.2 implementation commit:
`89778d4c449472677ae51e1f997d353780ea9396`.

V2.2 hosted evidence:
[CI Regression Gate run 33388903984](https://github.com/1yu-an/evaluation-first-governed-data-agent/actions/runs/33388903984).

This is a concise snapshot. The reviewer-facing source of truth is
[`03-governed-mysql-data-agent/README.md`](03-governed-mysql-data-agent/README.md),
with final hardening evidence in
[`V2_2_HARDENING_REPORT.md`](V2_2_HARDENING_REPORT.md).

## Feature status

The stable v1 behavior remains frozen. V2 adds strict external JSON Domain
Profiles, finite aggregate compilation, MySQL schema preflight, concise ask,
and no-execution explain. V2.2 hardens explicit scope handling, stable
secret-safe diagnostics, CLI help and environment defaults, minimal Profile
scaffolding, and the complete personal-user smoke flow. It adds no new
dependency or broad semantic path.

## Final architecture

```text
Question
→ Validated JSON Domain Profile
→ Profile-driven Resolver
→ SemanticPlan
→ Deterministic Compiler
→ AST SQL Policy
→ QueryExecutor
→ SQLite / MySQL
→ Database Least Privilege
→ Strict Result Verification
→ Eval / Benchmark / Regression Gate
```

## Verified results

- Project 03 ordinary suite: `223 passed, 1 skipped, 13 subtests passed`.
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

Local V2.2 acceptance used an isolated disposable MySQL Community Server
`8.0.46` on port 3307 and passed the real integration suite `10 / 10`.
`setup_mysql.py` ran as the admin/setup identity; the distinct `data_agent_ro`
runtime account had only `USAGE` plus `SELECT` on its target database. Direct
UPDATE, INSERT, and DELETE attempts were rejected by MySQL independently of the
application AST Policy. Both demo and expenses Profiles passed
`INFORMATION_SCHEMA` validation, and SQLite/MySQL evidence matched for the
three expenses metrics plus category filtering. The temporary instance and
data directory were stopped and removed after the run.

Hosted run `33388903984` independently passed the unified gate with disposable
MySQL `8.0.46`, including `10 / 10` real integration tests. Its toolchain was
Python `3.12.14`, Java `21.0.12.1`, and Maven `3.9.16`.

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
| `5c15f62` | add personal-use data agent Profiles |
| `5cc370a` | record v2 acceptance evidence |
| `89778d4` | harden personal data agent workflows for V2.2 |

## Compatibility and scope declaration

Do not broaden the default demo resolver, modify the fixed Eval Set, or pursue
56/56 as personal-use packaging work. New personal metrics belong in external Profiles,
not Core source. Web UI, LLM semantic parsing, RAG, agent frameworks, arbitrary
SQL, and schema auto-discovery remain outside the v2 MVP.
