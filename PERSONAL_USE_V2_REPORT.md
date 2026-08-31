# Personal-Use v2 Delivery Report

Verified on: 2026-08-31 (Asia/Shanghai)  
Stable v1 base: `5afe98c157d416a797b473c5bbea21c87cbdfdb0`  
Implementation branch: `codex/v2-personal-use`

## A. Outcome

The repository now contains a usable v2 Personal-Use Data Agent MVP. A user can
describe a governed personal schema in an external JSON Domain Profile, validate
the Profile offline and against real MySQL metadata, inspect a no-execution plan,
and ask supported aggregate questions through a concise CLI. The default demo
behavior remains backward compatible.

Final release status is assigned only after the branch is pushed and hosted CI
passes. Until then the implementation is locally complete but not release-closed.

## B. First-Principles Decision

Evidence showed that database execution, SQL policy, deterministic verification,
least privilege, and the fixed regression harness already worked. The blocker to
personal use was orders/payments/refunds knowledge embedded in catalog, resolver,
and compiler source. Therefore the lowest-cost architecture was Profile/Core
separation, not a new interface or model layer.

Rejected for this MVP:

- Web UI: changes presentation, not the source-edit requirement.
- LLM semantic parsing: expands ambiguity and evaluation scope before the
  deterministic configuration boundary is proven.
- RAG: retrieves context but does not create a safe executable metric contract.
- agent framework: adds orchestration without removing domain hard-coding.
- arbitrary SQL in config: turns the Profile into a policy bypass channel.
- Python/YAML runtime config: Python executes code; YAML adds a parser dependency
  and scalar ambiguity without improving the core proof.

## C. Product Flow

```text
copy/edit JSON Profile
→ validate-profile (offline)
→ optional MySQL INFORMATION_SCHEMA preflight
→ explain (resolve + compile + policy; executed=false)
→ ask (SELECT-only execution + strict result verification)
→ concise success or fail-closed reason
```

The non-demo `expenses` example supplies six rows, three metrics
(`total_expenses`, `expense_count`, `average_expense`), category aliases, and a
bound category filter. A complete SQLite path is:

```powershell
python scripts\init_expenses.py expenses.db
python -m src.cli validate-profile --profile profiles\expenses.json
python -m src.cli explain --profile profiles\expenses.json "average expense for transport"
python -m src.cli ask --profile profiles\expenses.json --db-path expenses.db "total expenses for groceries"
```

## D. Architecture

```text
JSON Profile → strict parser/reference validation ┐
                                                 ├→ SemanticPlan
Question → generic normalization/resolution ─────┘
    → finite aggregate/difference compiler
    → AST read-only SQL policy
    → SQLite or prepared MySQL executor
    → scalar ResultContract verification
    → answer contract
```

Core owns mechanics and safety. Profiles own metric language, finite dimension
values, allowed filters, and validated table/column operation metadata. Profiles
cannot add SQL text, functions, operators, credentials, or executable hooks.

## E. Profile and Schema Contracts

- JSON version 1 with strict required/unknown-field checks.
- Safe identifiers match `^[A-Za-z_][A-Za-z0-9_]*$`.
- Question-derived filter values always remain separate qmark parameters.
- Fixed predicates support equality and restricted literal characters only.
- Supported aggregate operations are count, sum, average, and maximum, plus the
  explicit v1-compatible difference of sums.
- Required table/column sets are derived from operations, not duplicated config.
- MySQL metadata uses one constant parameterized
  `INFORMATION_SCHEMA.COLUMNS` query.
- Missing objects fail as `SCHEMA_MISMATCH` before a business query.

## F. Implementation Inventory

- `src/profile.py`: immutable model, strict parser, cross-reference validation,
  default loader, and required-schema derivation.
- `profiles/demo.json`: all stable v1 domain metadata.
- `profiles/expenses.json`: non-demo personal example.
- `src/semantic.py` and `src/compiler.py`: generic Profile-driven Core.
- `src/schema_validation.py`: pure snapshot and real MySQL preflight.
- `src/agent.py`: selected Profile and no-execution explain.
- `src/cli.py`: legacy compatibility plus ask/explain/validate-profile.
- `scripts/init_expenses.py`, `sql/expenses_mysql.sql`, and updated MySQL setup.

## G. Test Evidence

- Project03: `203 passed, 1 skipped, 13 subtests passed`.
- New v2 coverage includes malformed/unsafe Profiles, duplicate phrases,
  reference errors, schema snapshots, metadata parameterization, all expenses
  metrics, filters, ambiguity, injection-shaped values, concise CLI output, and
  proof that explain never calls its executor.
- Project00 stable adapter: `9 passed`.
- Unified repository Local Acceptance Gate: every listed check passed and
  printed `FINAL RESULT: PASS`.
- Repository audit: PASS, zero HIGH/WARNING/INFO findings.
- Java: Project01 `3` tests and Project06 `2` tests passed on Java 21.

## H. Real MySQL and Security Evidence

An isolated local MySQL Community Server `8.0.46` was initialized in a new
temporary directory and bound to 127.0.0.1:3307. The setup/runtime identities
were distinct. Effective runtime grants were exactly USAGE and SELECT on
`data_agent.*`.

The real suite passed `10 / 10`:

- scalar cardinality enforcement;
- demo and expenses Profile metadata validation;
- SQLite/MySQL demo parity;
- SQLite/MySQL expenses parity for three metrics and category filtering;
- SELECT success;
- direct INSERT, UPDATE, and DELETE denial without relying on AST Policy.

The temporary server was shut down and its exact data directory removed.

## I. Benchmark and Regression Evidence

- Fixed Eval Set SHA-256:
  `FFA2D213867C1AD80F386EE2D762FD91224C215E23F91FC4A6B0A2F66675A40E`.
- Fixed system benchmark: `53 / 56` (`0.946429`).
- `SAFE_FAILURE=3`, `FALSE_SUCCESS=0`, `UNSAFE_ALLOW=0`, `OVER_BLOCK=0`.
- Regression Gate: PASS.
- Safety Invariants: PASS.
- The fixed Eval Set and gate thresholds were not modified.

## J. Git and Hosted CI

This section is completed after the implementation/evidence commits are pushed.
Required closure evidence is a clean worktree, branch tracking `origin`, and a
successful hosted workflow using MySQL 8.0.46, Python 3.12, Java 21, and Maven.

## K. Residual Boundaries

- This is a governed metric agent, not open-ended Text-to-SQL.
- A user must explicitly author metric operations; schema discovery is not an
  automatic business-semantics discovery mechanism.
- Only finite scalar aggregates and one governed difference operation exist.
- Verification proves result shape/value constraints, not independent business
  truth beyond the reviewed Profile/compiler contract.
- Local secrets remain environment variables; there is no production secret
  manager, pool, migration framework, or multi-tenant authorization layer.
- Web UI, LLM, RAG, and agent frameworks are intentionally deferred until the
  deterministic personal configuration boundary has real usage evidence.
