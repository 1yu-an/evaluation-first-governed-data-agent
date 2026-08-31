# V2.2 Productization Hardening PRD

Status: Approved for selective implementation

Audited baseline: `5cc370a0134afc0cfa781fc348990a86fe2d68e9`

Branch: `codex/v2-personal-use`

Audit date: 2026-08-31 (Asia/Shanghai)

## 1. Objective

Make the existing Personal-Use Data Agent easier to install, configure,
diagnose, and maintain for one long-term personal user without broadening its
query semantics or weakening its deterministic, read-only, fail-closed chain.

The optimization order is evidence first: remove confusion, simplify repeated
steps, improve errors, and only then add the smallest missing capability.

## 2. Baseline and Change Boundary

### Facts

- Git was clean before the audit. HEAD and upstream were both `5cc370a`; there
  were no staged, unstaged, or untracked files.
- V2 MVP already had successful local acceptance, real MySQL 8.0.46 integration,
  and hosted run `33369535514`.
- The fixed 56-case Eval Set SHA-256 was
  `FFA2D213867C1AD80F386EE2D762FD91224C215E23F91FC4A6B0A2F66675A40E`.
- The frozen result was 53/56 with `SAFE_FAILURE=3`, `FALSE_SUCCESS=0`,
  `UNSAFE_ALLOW=0`, and `OVER_BLOCK=0`.
- Runtime dependencies were exactly `sqlglot==30.13.0` and
  `mysql-connector-python==9.7.0`; `pip check` reported no broken requirements.

### Assumptions

- The primary user normally reuses one Profile and one SQLite/MySQL target for
  multiple questions.
- The user values a short, stable CLI contract more than interactive prompts or
  a new UI.
- Environment variables are acceptable for personal defaults and secrets, as
  long as CLI arguments have explicit precedence and no secret is printed.

### Inferences

- V2.2 should remain a narrow CLI/configuration hardening release.
- Java and Maven are repository acceptance dependencies, not personal Data
  Agent runtime dependencies.
- New third-party packages are unnecessary for the observed problems.

### Unknowns

- How often the user switches among multiple databases in one day.
- Whether the user wants a human text output in addition to the current pretty
  JSON output.
- Whether schema inspection would replace an existing database GUI/CLI in the
  user's real workflow.

## 3. Audit Method

The current documented journey was executed before any implementation change:

```text
Install/dependency check
→ CLI help
→ demo SQLite query
→ expenses SQLite initialization
→ offline Profile validation
→ no-execution explain
→ concise ask
→ invalid Profile
→ invalid credentials / refused connection
→ unknown metric
→ unsupported filter
→ ambiguous query
→ schema mismatch
→ demo + expenses real MySQL validation and ask
```

The audit used disposable SQLite files and a disposable MySQL Community Server
8.0.46 on 127.0.0.1:3307. Temporary databases were removed after execution.

## 4. Real User Friction

### 4.1 P0 — Explicit scope can be silently dropped

**Fact**

- `explain --profile profiles/expenses.json "total expenses for the north
  region"` returned `status=OK`, `filters={}`, and compiled the unfiltered total.
- `"total expenses for category business"` behaved the same way.
- The default demo correctly rejected a declared but unsupported status filter:
  `completed_orders with status pending` stopped before execution.

**Assumption**

- A personal user will naturally try dimension labels and values that are not
  valid for every metric.

**Inference**

- The Core fail-closed mechanism already works when the Profile declares the
  filter vocabulary. The expenses Profile does not declare enough adjacent
  labels/known unsupported dimensions, so the lowest-risk correction is to
  harden Profile coverage and its generated template rather than add an open
  natural-language parser.

**Unknown**

- No finite Profile can recognize every possible unknown modifier. The tool
  must continue documenting that governed scope vocabulary is explicit.

### 4.2 P1 — Database failures are distinguishable only through vendor text

**Fact**

- Refused connection produced a generic `MySQL schema inspection failed`
  prefix followed by MySQL error 2003.
- Bad credentials produced the same prefix followed by error 1045.
- A database permission failure produced 1044; an empty but readable database
  produced the clear `SCHEMA_MISMATCH: missing table expenses` result.
- Windows localized socket text was mojibake in the captured output.
- None of the outputs exposed the supplied test password.

**Assumption**

- Most users understand `database_connection_refused` more quickly than MySQL
  numeric codes and localized driver text.

**Inference**

- A small errno-to-category mapping plus stable `reason_code` and one repair
  hint will materially reduce diagnosis time without creating an error
  framework.

**Unknown**

- Some managed MySQL proxies may reuse or omit standard connector errno values;
  unknown errors must retain a safe generic fallback.

### 4.3 P1/P2 — Bootstrap and repeated configuration are inconsistent

**Fact**

- `python -m src.cli --help` was interpreted as a business question, returned
  `NEED_CLARIFICATION`, and exited 0.
- Subcommand help existed but showed only bare argument names.
- The personal quickstart appeared before the full install instructions and
  assumed the user was already in the Project03 directory with dependencies
  installed.
- The documented repository setup used `requirements-dev.txt`; personal runtime
  needs only Project03 `requirements.txt` and does not require Java/Maven.
- `DATA_AGENT_PROFILE` worked. Explicit `--profile` overrode it.
- `DATA_AGENT_DB_PATH` was ignored. With the environment variable set to a valid
  expenses database, omitting `--db-path` still opened `demo.db` and failed with
  `no such table: expenses`.

**Assumption**

- Profile and database path are the two most frequently repeated SQLite CLI
  arguments.

**Inference**

- Root help, minimal install documentation, and one database-path environment
  default provide more value than a layered configuration file.

**Unknown**

- There is no evidence yet that aliases, named environments, or multiple config
  files are needed.

### 4.4 P1/P2 — Creating the first valid Profile starts from too much JSON

**Fact**

- `profiles/expenses.json` contained 111 lines; `profiles/demo.json` contained
  267 lines.
- There was no `init-profile` command.
- Common errors were path-qualified but repair-light:
  - unsupported aggregate `average` did not list supported values;
  - duplicate synonyms reported the array path and `duplicate values`;
  - missing columns and unsafe identifiers were located precisely.

**Assumption**

- Copying a domain-specific 111-line example encourages accidental retention of
  irrelevant metrics and filters.

**Inference**

- A legal one-metric scaffold with placeholders and immediate offline
  validation is a small, high-value addition. It must not inspect data, infer
  metrics, or generate SQL.

**Unknown**

- The preferred first metric varies by personal database; the template should
  therefore use explicit `replace_me` identifiers and explain the next edits.

### 4.5 P2 — Output and explain are already adequate

**Fact**

- New `ask` output was pretty JSON with stable success fields and no SQL or
  credentials.
- Failure output was also JSON, but safe-failure statuses/reasons were not yet
  normalized for automation.
- `explain` showed Profile, resolved metric/filters, SemanticPlan, parameterized
  SQL, bound parameters, qmark style, policy decision, `executed=false`, and
  trace.
- A test injected an executor that fails if explain attempts execution.

**Assumption**

- Pretty JSON is acceptable for both current human use and shell automation.

**Inference**

- Adding `--json` would duplicate the current output mode. Adding `--debug`
  would duplicate explain/legacy detail. The useful change is a stable failure
  `reason_code`, included with diagnostics work.

**Unknown**

- Human text output may be reconsidered only after real daily use feedback.

## 5. Candidate Ranking

| Candidate | Problem | Evidence | Benefit | Cost | Risk | ROI | Decision |
|---|---|---|---|---|---|---|---|
| 1. Explicit scope hardening | A declared-looking filter can disappear and return an unfiltered number | Two expenses explain commands returned OK with empty filters | Prevents observed wrong-success path | Low | Low if kept Profile-driven | Very high | Implement (P0) |
| 2. Actionable diagnostics + reason codes | DB/Profile errors require vendor-code knowledge and are weak for automation | Actual 2003/1045/1044 outputs; aggregate error omitted allowed values | Faster repair, stable safe-failure contract | Low-medium | Low with fallback and secret tests | Very high | Implement (P1) |
| 3. CLI bootstrap/defaults | Root help is broken; DB path must be repeated; runtime install is buried | Actual help exit 0 and ignored `DATA_AGENT_DB_PATH` | Fewer steps and less repeated typing | Low | Low | Very high | Implement (P1/P2) |
| 4. `init-profile` scaffold | First Profile otherwise starts from 111+ domain-specific lines | Measured Profile sizes and no scaffold command | Faster valid starting point, fewer syntax errors | Low-medium | Low with no-overwrite behavior | High | Implement (P1/P2) |
| 5. `inspect-schema` | Users may need table/column/type context | Metadata code exists, but no observed user blocker or usage frequency | Could reduce switching to DB tools | Medium | Medium: types/cross-dialect contract | Unproven | Defer |
| 6. `--json` mode | Automation needs structured output | Current ask/explain/errors already emit JSON | Little incremental benefit | Low | Adds redundant mode contract | Low | Reject for V2.2 |
| 7. `--debug` mode | Developers may want internal stages | Explain and legacy output already expose stages without secrets | Mostly duplicate visibility | Medium | Risk of secret/noise regressions | Low | Reject for V2.2 |
| 8. New `--offline`/`--database` validation modes | Static and DB validation should be distinct | Existing command already distinguishes no flag vs `--check-mysql-schema` and reports `mysql_schema_checked` | Naming-only change | Low | Compatibility/documentation churn | Low | Keep existing design |

Exactly four changes are selected. No other audit finding enters implementation.

## 6. Selected Requirements

### H-1 Profile-driven explicit scope hardening

- The expenses Profile must recognize `category <value>` and `<value> category`.
- It must also recognize finite known-but-unsupported filter concepts such as
  `region` and `status`, while no expenses metric allows them.
- The existing compiler must then reject the field/value before execution.
- Tests must prove the two observed queries no longer compile or execute.
- Do not add an open-ended scope parser or domain constants to Core.

### H-2 Actionable, secret-safe diagnostics

- New CLI error objects must include a stable `reason_code`.
- MySQL schema inspection must minimally classify:
  - host not found;
  - connection refused/unavailable;
  - authentication failed;
  - database unavailable/not found when the connector reports it;
  - permission denied;
  - schema mismatch;
  - generic inspection failure.
- Known categories must include a short, non-secret repair hint.
- Profile enum errors must list supported values where low-cost.
- New `ask` safe failures must normalize to `status=safe_failure` and a stable
  reason code without changing `DataAgent`'s v1 compatibility contract.
- Driver detail may remain for diagnosis, but passwords, DSNs, environment
  values, and tracebacks must never be included.

### H-3 CLI bootstrap and configuration precedence

- Root `-h/--help` must show the command list and exit 0 without resolving a
  business question.
- Add `DATA_AGENT_DB_PATH` for SQLite.
- Precedence must be:

```text
explicit CLI argument > environment variable > default demo.db
```

- Preserve the existing `DATA_AGENT_PROFILE` precedence using the same rule.
- Help text and README must show defaults, environment variables, minimal
  Project03 runtime installation, and that Java/Maven/MySQL are not required for
  the SQLite personal quickstart.
- Do not add a config file or dependency.

### H-4 Minimal Profile scaffold and smoke flow

- Add `python -m src.cli init-profile PATH`.
- Generate a legal Profile v1 containing one explicit placeholder count metric.
- Derive a valid Profile ID from a valid filename stem or accept an explicit
  safe ID; invalid stems must return an actionable error.
- Refuse to overwrite an existing path.
- Never connect to a database, inspect data, infer business meaning, generate
  raw SQL, or create credentials.
- Validate the generated object with the production Profile validator before
  writing it.
- Add one end-user smoke test covering:

```text
initialize expenses DB
→ validate Profile
→ explain question (executed=false)
→ ask question
→ expected value 47.5
```

## 7. Output Contract

Successful new-style `ask` remains:

```json
{
  "status": "success",
  "profile_id": "expenses",
  "metric": "total_expenses",
  "filters": {"category": "food"},
  "value": 47.5,
  "verified": true,
  "evidence": {"row_count": 1, "result_key": "total_expenses"}
}
```

A safe semantic failure should become:

```json
{
  "status": "safe_failure",
  "reason_code": "unknown_metric",
  "reason": "unknown business metric",
  "evidence": {}
}
```

A configuration/database failure should use `status=error`, a stable
`reason_code`, the non-secret detail, optional repair hint, and empty evidence.

## 8. Security and Architecture Invariants

- Natural language must still flow through SemanticPlan, finite compiler, AST
  SQL policy, read-only executor, and verification.
- Profiles cannot add raw SQL, executable hooks, credentials, functions, or
  compiler operations.
- Scaffold output is data only and passes the same validator as user Profiles.
- Scope hardening must feed existing filter validation, not bypass it.
- Database diagnostics must classify exceptions without serializing connection
  kwargs or environment values.
- Explain must remain no-execution.
- No third-party dependency may be added.

## 9. Focused Test Plan

### Scope

- expenses category label with an unsupported value fails before execution;
- expenses region/status filter fails before execution;
- valid groceries/transport filters remain bound and executable;
- demo behavior remains unchanged.

### Diagnostics and output

- MySQL errno categories and generic fallback;
- safe failure reason codes for unknown metric, ambiguous metric, and unsupported
  filter;
- no test secret appears in normal, error, or hinted output;
- Profile invalid aggregate lists the supported values.

### CLI configuration

- root help;
- CLI Profile/DB path overrides environment;
- environment overrides default;
- missing MySQL configuration remains nonzero and actionable.

### Scaffold and smoke

- generated Profile loads and passes offline validation;
- existing target is not overwritten;
- invalid Profile ID fails cleanly;
- command performs no database connection;
- complete expenses smoke flow succeeds.

## 10. Regression and Acceptance

After each selected change: run its focused tests, then existing Project03
regression before the next change.

Final evidence must include:

- `pip check`;
- Project00, Project02, Project03, Project04, and Project05 Python tests;
- Project01 and Project06 Maven tests;
- repository audit and audit tests;
- disposable real MySQL integration;
- fixed 56-case Benchmark, Regression Gate, and Safety Gate;
- exact unchanged Eval SHA;
- repository Acceptance Gate;
- `git diff --check`;
- clean committed branch pushed to origin;
- successful hosted GitHub Actions.

V2.2 is DONE only if all required evidence passes, the worktree is clean, and
the documentation describes the actual behavior. Otherwise it remains partial.

## 11. Explicit Non-Goals

No Web UI, React, FastAPI, LLM, RAG, embeddings, vector database, agent
framework, Redis, authentication, multi-user layer, cloud deployment, Docker
orchestration, ORM, plugin system, arbitrary SQL, schema auto-discovery, config
framework, logging platform, or broad module refactor will be added.

`inspect-schema`, human text output, multiple named environments, and database
type compatibility checks remain evidence-gated future candidates.
