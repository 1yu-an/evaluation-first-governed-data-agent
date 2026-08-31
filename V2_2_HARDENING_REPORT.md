# V2.2 Productization Hardening Report

Status: DONE

Verified: 2026-08-31 (Asia/Shanghai)

Branch: `codex/v2-personal-use`

Implementation commit: `89778d4c449472677ae51e1f997d353780ea9396`

This report closes the evidence-backed hardening scope selected in
[`V2_2_HARDENING_PRD.md`](V2_2_HARDENING_PRD.md). V2.2 changes the personal
user journey, diagnostics, and Profile safety coverage. It does not broaden
the frozen default semantics, fixed Eval Set, compiler operation set, or
database privileges.

## A. Starting State

- The audit started from clean commit
  `5cc370a0134afc0cfa781fc348990a86fe2d68e9`; HEAD and upstream matched and
  there were no staged, unstaged, or untracked files.
- Stable v1 remained rooted at
  `5afe98c157d416a797b473c5bbea21c87cbdfdb0`.
- The existing v2 Profile architecture, real MySQL path, and hosted acceptance
  were already working. V2.2 was therefore treated as selective hardening, not
  a rewrite.
- Runtime dependencies remained exactly `sqlglot==30.13.0` and
  `mysql-connector-python==9.7.0`.

## B. End-User UX Audit

The documented install and usage journey was executed before implementation:

```text
install/dependency check
-> root and subcommand help
-> demo SQLite ask
-> expenses SQLite initialization
-> Profile validation
-> explain without execution
-> ask
-> invalid Profile
-> refused connection / bad credentials / permission failure
-> unknown, ambiguous, and unsupported questions
-> schema mismatch
-> real MySQL validation and ask
```

The audit found four evidence-backed friction clusters:

1. P0: `total expenses for the north region` and `total expenses for category
   business` produced an apparently valid unfiltered plan because the Profile
   did not declare enough scope vocabulary.
2. P1: MySQL 2003, 1045, and 1044 failures were distinguishable mainly through
   vendor detail, while localized Windows detail was not consistently readable.
3. P1/P2: root `--help` was treated as a business question,
   `DATA_AGENT_DB_PATH` was ignored, and the personal runtime installation path
   was buried beneath repository-wide developer prerequisites.
4. P1/P2: the first custom Profile had to start by copying a domain-specific
   111- or 267-line example; no minimal scaffold existed.

Facts, assumptions, inferences, unknowns, exact observations, and the full
candidate table are retained in the PRD rather than reconstructed after the
implementation.

## C. Candidate Ranking and Selection

Eight candidates were ranked by observed evidence, user benefit, cost, risk,
and ROI. Exactly four were selected:

| Rank | Candidate | Priority | Decision basis |
|---:|---|---|---|
| 1 | Profile-driven explicit scope hardening | P0 | Prevents an observed wrong-success path with low Core risk |
| 2 | Actionable diagnostics and stable reason codes | P1 | Reduces diagnosis time without a new framework |
| 3 | CLI bootstrap and environment defaults | P1/P2 | Removes repeated arguments and a broken help entrypoint |
| 4 | Minimal `init-profile` scaffold and smoke flow | P1/P2 | Provides a safe first Profile without data inference |

No unranked feature entered the implementation.

## D. Implemented Changes

### D.1 Explicit scope remains Profile-driven

- The expenses Profile recognizes explicit `category`, `region`, and `status`
  scope vocabulary.
- Valid category values still compile to bound parameters.
- Unsupported category values and the known unsupported region/status fields
  reach the existing compiler validation and stop before SQL execution.
- No open-ended natural-language parser or expenses-specific Core constant was
  added.

### D.2 Actionable, secret-safe failures

- New-style `ask` normalizes governed semantic stops to
  `status=safe_failure`, a stable `reason_code`, and empty evidence.
- Configuration and database problems use `status=error` with a stable reason
  code and short repair hint.
- MySQL diagnostics classify host lookup, connection availability,
  authentication, database absence, permission denial, schema mismatch, and a
  safe generic fallback.
- Profile enum validation now lists supported values where useful.
- The configured password is redacted from retained driver detail.

### D.3 Shorter bootstrap and stable precedence

- Root `-h/--help` now prints commands and exits 0 without loading the executor
  or resolving a question.
- SQLite selection now follows:

```text
explicit --db-path > DATA_AGENT_DB_PATH > demo.db
```

- Profile selection consistently follows:

```text
explicit --profile > DATA_AGENT_PROFILE > profiles/demo.json
```

- The personal quickstart installs only Project03 runtime requirements and
  states that Java, Maven, and MySQL are not required for the SQLite path.

### D.4 Minimal Profile scaffold and smoke journey

- `python -m src.cli init-profile PATH [--profile-id ID]` writes a legal,
  validator-approved Profile v1 with one placeholder count metric.
- The command refuses overwrite, accepts only safe IDs, creates no credentials,
  includes no raw SQL, and performs no database access or schema inference.
- A single automated user journey covers initialize expenses, validate via the
  environment default, explain with `executed=false`, and ask with value 47.5.

## E. Rejected or Deferred Work

The following attractive-looking additions were deliberately not implemented:

- `inspect-schema`: metadata support exists, but the audit found no real user
  blocker or usage frequency sufficient to justify a new cross-dialect output
  contract.
- `--json`: current ask, explain, validation, scaffold, and failure output are
  already structured JSON.
- `--debug`: explain and legacy output already expose the governed stages;
  another mode would add noise and secret-regression risk.
- New `--offline` and `--database` validation commands: the existing flag
  already makes the distinction without compatibility churn.
- Human text output, named environments, config frameworks, schema
  auto-discovery, and type compatibility checks: no current evidence supports
  their cost.
- Web UI, FastAPI, React, LLM parsing, RAG, embeddings, vector databases, agent
  frameworks, auth, multi-user support, cloud deployment, Redis, ORM, Docker
  orchestration, plugins, and arbitrary SQL: all remain explicit non-goals.

## F. Before and After

| User task | Before | V2.2 |
|---|---|---|
| Discover commands | Root help became a business query | Root help lists commands, exits 0, and does not load execution |
| Reuse SQLite target | `DATA_AGENT_DB_PATH` was ignored | CLI, environment, and demo fallback have tested precedence |
| Diagnose MySQL auth/network | Generic prefix plus vendor code | Stable reason code, repair hint, redacted detail |
| Handle unsupported expenses scope | Some explicit scope disappeared into an unfiltered plan | Known category/region/status scope stops before execution |
| Start a Profile | Copy 111-267 domain-specific lines | Generate one legal minimal metric and edit explicit placeholders |
| Verify daily journey | Separate examples only | One initialize -> validate -> explain -> ask smoke test |

The successful `ask` JSON contract and no-execution explain detail remain
unchanged where they were already adequate.

## G. Verification Evidence

### Focused and Project03 tests

- Final diagnostics-focused suite: `24 passed`.
- Project03 full suite: `223 passed, 1 skipped, 13 subtests passed`.
- The new tests cover scope rejection before execution, reason-code mapping,
  password redaction, help/default precedence, scaffold validation and
  no-overwrite behavior, no database access during scaffolding, and the full
  expenses smoke flow.

### Unified local gate

`python scripts/acceptance_gate.py` returned `FINAL RESULT: PASS`:

| Check | Result |
|---|---:|
| Repository validation | PASS |
| Repository audit tests | 17 passed |
| Repository audit | PASS; HIGH=0, WARNING=0, INFO=0 |
| Acceptance-gate tests | 9 passed |
| Project00 Python | 59 passed |
| Project02 Python | 2 passed |
| Project03 Python | 223 passed, 1 skipped, 13 subtests |
| Project04 Python | 1 passed |
| Project05 Python | 1 passed |
| Project01 Maven | 3 tests; BUILD SUCCESS |
| Project06 Maven | 2 tests; BUILD SUCCESS |
| Project03 Benchmark Gate | PASS |

Additional local checks:

- `python -m pip check`: `No broken requirements found`.
- `git diff --check`: passed.
- No new third-party dependency was added.

### Real MySQL 8.0.46

An isolated local MySQL Community Server 8.0.46 on port 3307 was initialized,
seeded through the production setup script, tested, stopped, and removed.

- Effective runtime grants were exactly `USAGE ON *.*` and
  `SELECT ON data_agent.*`.
- Real integration suite: `10 passed`.
- Expenses Profile `INFORMATION_SCHEMA` validation returned `status=valid` and
  `mysql_schema_checked=true`.
- Real user query `total expenses for groceries` returned 47.5,
  `verified=true`, and one evidence row.
- Final cleanup evidence: server stopped, port 3307 free, and temporary data
  directory absent.

## H. Fixed Benchmark and Compatibility

The fixed case file SHA-256 is unchanged:

```text
FFA2D213867C1AD80F386EE2D762FD91224C215E23F91FC4A6B0A2F66675A40E
```

`tests/test_integration_03.py` passed all 9 tests. The standalone 56-case gate
reported:

| Measure | Result |
|---|---:|
| Successful cases | 53 / 56 |
| Outcome / conformance / state / policy / overall | 0.946429 |
| Verification | 0.875000 |
| SAFE_FAILURE | 3 |
| FALSE_SUCCESS | 0 |
| UNSAFE_ALLOW | 0 |
| OVER_BLOCK | 0 |
| Regression Gate | PASS |
| Safety Invariants | PASS |

The three deliberate ambiguous cases remain safe failures. V2.2 does not chase
56/56 or change the default demo resolver.

## I. Security and Architecture Review

- Natural language still passes through Profile validation, deterministic
  resolution, `SemanticPlan`, finite compiler templates, AST SQL policy,
  read-only execution, and strict result verification.
- A Profile still cannot add SQL, code, hooks, credentials, or compiler
  operations.
- Scope hardening feeds existing compiler validation rather than bypassing it.
- Explain remains provably no-execution.
- Scaffold output is data-only and is checked by the production validator
  before exclusive creation.
- Diagnostics never serialize connector kwargs, environment contents, DSNs,
  tracebacks, or the configured password.
- MySQL independently enforces least privilege even if an application-layer
  error were introduced.
- Repository secret scanning finished with zero findings.

## J. Known Limitations

- Governed scope recognition is finite. An entirely unknown modifier that does
  not match Profile vocabulary cannot always be distinguished from harmless
  prose without adding open-ended semantic inference.
- Profiles remain manually authored after scaffolding; the tool intentionally
  does not infer business meaning from schema or data.
- MySQL proxies may omit or remap standard connector errno values; these use the
  generic, secret-safe fallback.
- Output remains pretty JSON only. Human text output is evidence-gated future
  work.
- SQLite is the zero-service personal default. Local MySQL remains opt-in and
  requires a separately provisioned read-only account.

## K. Git and Hosted CI Evidence

- Implementation commit:
  `89778d4c449472677ae51e1f997d353780ea9396`.
- The commit was pushed normally to `origin/codex/v2-personal-use`; no force
  push, reset, clean, or user-change deletion was used.
- Hosted [CI Regression Gate run 33388903984](https://github.com/1yu-an/evaluation-first-governed-data-agent/actions/runs/33388903984)
  completed successfully for the exact implementation SHA.
- Hosted toolchain: Python 3.12.14, Java 21.0.12.1, Maven 3.9.16, and disposable
  MySQL 8.0.46.
- Hosted evidence repeated the 223-test Project03 suite, 10-test real MySQL
  suite, both Maven builds, repository audit, fixed Benchmark, Safety Gate, and
  `FINAL RESULT: PASS`.

All four selected changes and every required local, database, benchmark,
security, Git, and hosted acceptance condition passed. V2.2 is DONE.
