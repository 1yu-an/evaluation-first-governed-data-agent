# v2 Personal-Use Data Agent PRD

Status: **Approved for MVP implementation**  
Date: 2026-08-31 (Asia/Shanghai)  
Stable v1 base: `5afe98c157d416a797b473c5bbea21c87cbdfdb0`  
Development branch: `codex/v2-personal-use`

## 1. Problem

The stable Project 03 system proves a governed query pipeline against one demo
domain, but it is not yet a practical personal tool for an arbitrary user-owned
MySQL database. Connecting to another database is already possible at the
transport layer; teaching the Agent that database's approved business meaning
still requires editing Python source.

The specific usability gap is:

> A user cannot define a new finite set of metrics, synonyms, table/column
> mappings, and allowed filters outside the Agent implementation, validate that
> definition against the real database, and query it through the existing
> fail-closed pipeline.

### 1.1 Facts

The following statements are verified from the current files and tests.

1. `src/catalog.py` embeds all seven demo metric IDs, business meanings,
   synonyms, composition rules, filter allowlists, result contracts, and
   metric-specific compiler strategy values in Python.
2. `src/semantic.py` imports the global demo catalog and embeds demo token
   normalization, payment/refund/order guard rules, `region`/`status` parsing,
   and the Chinese ambiguity marker.
3. `src/compiler.py` embeds the four allowed region values, all demo
   table/column names, completed/pending predicates, joins, aggregations, and
   one Python compiler function per demo metric.
4. `src/demo.py`, `schema_mysql.sql`, and `scripts/setup_mysql.py` create and
   seed only the orders/payments/refunds demo domain.
5. `src/cli.py` treats all arguments as one question, defaults to `revenue`,
   cannot select or validate a profile, and has no non-executing explain flow.
6. `MySQLConfig.from_env()` already accepts `MYSQL_HOST`, `MYSQL_PORT`,
   `MYSQL_DATABASE`, `MYSQL_AGENT_USER`, and `MYSQL_AGENT_PASSWORD`.
7. The MySQL runtime rejects root or a shared admin identity. The hosted
   integration environment proves the runtime account has only `USAGE` plus
   `SELECT` and that INSERT/UPDATE/DELETE are denied by MySQL.
8. The compiler already separates SQL from bound filter parameters. The MySQL
   executor uses prepared cursors and never falls back silently when MySQL
   configuration is missing.
9. AST Policy, strict scalar result verification, the 56-case Benchmark, and
   the risk-weighted safety gate already exist and pass.
10. The fixed 56-case Eval Set SHA-256 is
    `FFA2D213867C1AD80F386EE2D762FD91224C215E23F91FC4A6B0A2F66675A40E`.
11. The current branch baseline is 53/56 with `SAFE_FAILURE=3`,
    `FALSE_SUCCESS=0`, `UNSAFE_ALLOW=0`, and `OVER_BLOCK=0`.
12. Current Project 03 tests pass: `172 passed, 1 skipped, 13 subtests passed`;
    the Project 00 integration module passes `9/9`.

### 1.2 Assumptions

1. The personal user can provision or obtain a dedicated SELECT-only MySQL
   account. The application will never elevate that account.
2. One profile targets one configured MySQL database at a time.
3. MVP metrics return one numeric scalar. Tables, columns, joins, fixed
   predicates, and filter values are finite and explicitly approved.
4. Personal filter dimensions have a finite configured vocabulary or mapping;
   unrecognized values must fail closed.
5. A read-only MySQL user with privileges on the target objects can see the
   relevant rows in `INFORMATION_SCHEMA.COLUMNS`.
6. JSON editing is acceptable for the sole current user if errors include an
   exact path and actionable reason.

### 1.3 Inferences

1. A new UI, LLM, Agent framework, or orchestration layer would not remove the
   need to edit Python for every new metric; those additions do not address the
   current bottleneck.
2. Moving domain knowledge into a validated external profile is lower cost and
   lower risk than making the resolver or SQL generator open-ended.
3. A profile must describe approved semantic components, never raw SQL. A
   finite compiler can then remain the sole owner of SQL structure.
4. Schema validation is necessary before execution because static profile
   validation cannot prove that configured tables and columns exist in the
   selected database.
5. The existing demo must become the default external profile so the same
   public interfaces and Benchmark can prove backward compatibility.

### 1.4 Unknowns

1. The user's eventual production table/column names and metric definitions are
   unknown; the contract must be domain-neutral.
2. The user's MySQL network/TLS requirements are unknown. MVP retains the
   current connector options and environment contract rather than inventing
   deployment policy.
3. Very large or frequently changing filter vocabularies may eventually need a
   different model. MVP intentionally uses finite mappings.
4. The deterministic resolver may be insufficient for some future natural
   language phrasing. That is evidence for a later semantic-input phase, not a
   reason to add an LLM now.

## 2. First-Principles Decision

### Decision

**Proceed with Domain Profile + Core Engine + Database Config separation.**

This is the minimum-cost path from demo prototype to personal tool because:

- Database connectivity and least-privilege execution already work.
- Safety policy and result verification already work.
- The blocking variable is domain knowledge embedded in source.
- External, validated declarative data removes that source-edit requirement
  while leaving all execution decisions deterministic.

### Rejected shortcuts

| Shortcut | Why it does not meet the goal |
|---|---|
| Add another hard-coded expenses strategy | Demonstrates a second demo but still requires Python edits for the user's database. |
| Allow SQL in a config file | Makes “configurable” equivalent to arbitrary SQL and weakens the safety boundary. |
| Scan the database and guess metrics | Table structure cannot establish business meaning; false-success risk rises. |
| Add an LLM | Does not replace the need for an approved metric contract and introduces a nondeterministic input boundary. |
| Add Web/API layers | Changes presentation, not domain portability or correctness. |

## 3. Goal

Deliver a small v2 MVP that lets one user:

1. keep MySQL credentials outside Git;
2. create a validated external Domain Profile;
3. define a finite set of numeric metrics, synonyms, and allowed filters;
4. validate that profile statically and against the configured MySQL schema;
5. ask deterministic natural-language questions through the existing governed
   pipeline;
6. inspect the resolved plan, compiled SQL, bound parameters, and policy result
   without execution;
7. receive a clear answer or actionable fail-closed reason; and
8. preserve every v1 benchmark and safety invariant.

The user must not edit `src/agent.py`, `src/semantic.py`, `src/compiler.py`, or
other Core Engine source to onboard a new profile.

## 4. Non-Goals

The v2 MVP will not implement:

- arbitrary natural-language-to-SQL generation;
- raw SQL stored in profiles;
- automatic metric inference from database metadata;
- full schema discovery or catalog browsing;
- multiple databases in one query;
- PostgreSQL or another new backend;
- a Web UI, HTTP API, login system, cloud deployment, SaaS, or multi-tenancy;
- React, FastAPI, LangChain, LangGraph, RAG, a vector database, Redis,
  Kubernetes, an ORM, or a multi-Agent system;
- an LLM dependency;
- write execution, schema migration, or privilege elevation;
- INSERT, UPDATE, DELETE, DDL, locking reads, or multiple statements;
- dashboards, free-form reporting, grouping, or multi-row results;
- unbounded filter values or dynamic user-provided identifiers.

## 5. Core User and Use Cases

### User

One technical personal user who owns or can access a MySQL database and can
prepare a SELECT-only runtime identity.

### Primary flow

```text
Copy .env.example
→ configure SELECT-only MySQL identity
→ copy/edit a Domain Profile JSON file
→ run static profile validation
→ run MySQL schema validation
→ explain a question without execution
→ ask the question
→ receive status, metric, filters, value, and evidence
```

### Failure flows

- Invalid JSON/profile shape: return `PROFILE_INVALID` and a field path.
- Unknown table/column: return `SCHEMA_INVALID` before a business query runs.
- Missing connection setting: return `ERROR` with the missing variable.
- Unknown/ambiguous metric: return `NEED_CLARIFICATION`; emit no SQL/value.
- Unsupported filter/value: return `NEED_CLARIFICATION`; emit no query.
- SQL Policy rejection: return `BLOCKED`; do not execute.
- Database/result failure: return `ERROR`; emit no verified business value.

## 6. MVP Scope

### Must Have

1. Versioned external Domain Profile contract.
2. External metric IDs, meanings, canonical forms, synonyms, and deterministic
   composition patterns.
3. External filter dimensions, phrase forms, allowed value mappings, and
   per-metric allowlists.
4. Finite compiler operations for scalar `COUNT`, `SUM`, `AVG`, `MAX`, and the
   existing demo's difference-of-sums revenue operation.
5. Identifier and profile validation that rejects unknown fields, duplicate
   metric/synonym ownership, invalid aggregations, unsafe identifiers, missing
   sources, and invalid filter references.
6. MySQL metadata validation for every referenced table and column.
7. Profile injection into resolver/compiler/Agent while keeping the demo
   profile as the default.
8. CLI commands for profile validation, explain, and ask.
9. One external personal-expenses profile with at least three metrics, one
   filter dimension, and at least five rows in test data.
10. Non-demo MySQL execution through the existing read-only account.
11. Full v1 test/Benchmark/safety compatibility.

### Should Have

- Concise user-facing CLI JSON that separates status, metric, filters, value,
  evidence, and failure reason.
- `--debug` output retaining the full internal trace when needed.
- Explain output containing resolved metric/filters, SQL, params, and policy
  decision without opening a database connection.

### Nice to Have — explicitly deferred

- Web UI, dashboard, LLM, RAG, Agent framework, automatic schema discovery,
  multi-database support, and cloud deployment.

## 7. Functional Requirements

### FR-1 Profile loading

- Load UTF-8 JSON from an explicit CLI path or `DATA_AGENT_PROFILE`.
- Use the tracked demo profile when neither is supplied.
- Reject unreadable files, malformed JSON, wrong versions, unknown keys, and
  invalid values with stable error types and field paths.

### FR-2 Resolver

- Resolve only profile-owned canonical forms, synonyms, and composition rules.
- Detect multiple metric candidates and configured guard rules.
- Extract configured filter dimensions without accepting unknown dimensions.
- Preserve an unknown value adjacent to a known filter phrase so compilation
  fails closed rather than silently dropping scope.

### FR-3 Deterministic compilation

- Select one finite operation from validated profile data.
- Build identifiers only from validated profile identifiers.
- Keep question-derived filter values in bound params.
- Never accept SQL text, SQL fragments, functions, operators, or clauses from
  the user/profile.
- Continue passing every compiled query through AST Policy.

### FR-4 Static profile validation

- Reject missing metrics, duplicate IDs, duplicate synonym ownership, invalid
  aggregation/operation kinds, invalid identifiers, missing operation fields,
  bad join definitions, unknown filters, unsupported result-key modes, and
  malformed guard/composition rules.

### FR-5 MySQL schema validation

- Query a fixed `INFORMATION_SCHEMA.COLUMNS` statement with a bound database
  parameter.
- Compare the result to the validated profile's required tables/columns.
- Report every missing table/column together and perform no business query.
- Do not create/alter tables, users, or grants.

### FR-6 CLI

- `validate-profile`: static validation, with an explicit MySQL schema-check
  option.
- `explain`: resolve, compile, and apply policy without execution.
- `ask`: run the complete governed chain.
- Keep the legacy one-question invocation working for the default demo.
- Catch expected configuration/connection/profile errors without a Python
  traceback in normal mode.

### FR-7 Answer contract

Success must expose:

- `status`
- `metric`
- `filters`
- `value`
- `evidence`
- `verified`

Failures must expose:

- `status`
- `failure_reason` (and backward-compatible `reason` where already present)
- resolved metric/filters when known
- no verified value or evidence

SQL and params remain available in the internal result and explain/debug mode;
normal CLI output need not display them.

## 8. Security Requirements

1. `FALSE_SUCCESS=0` and `UNSAFE_ALLOW=0` remain hard gates.
2. Profile files cannot contain SQL or credentials.
3. Every identifier is syntax-validated before compilation and existence-
   validated before real use.
4. Every question-derived value is bound, never interpolated.
5. Every compiled statement passes the current AST read-only policy.
6. Runtime root/admin identities remain rejected.
7. No fallback to SQLite occurs after MySQL is explicitly selected.
8. Schema validation is read-only.
9. Secrets and connection strings never appear in answer/explain output.
10. Database-level SELECT-only grants continue to deny writes independently of
    application policy.

## 9. Personal Example Acceptance

The tracked example will use an `expenses` table with at least six rows.

Profile metrics:

1. `total_expenses` — SUM of amount.
2. `expense_count` — COUNT of rows.
3. `average_expense` — AVG of amount.

Filter dimension:

- `category`, with a finite alias-to-database-value mapping.

Acceptance questions include unfiltered and filtered forms such as total
expenses, number of expenses, average expense, and total expenses for the
groceries category.

## 10. Test Strategy

### Profile tests

- valid demo and personal profiles;
- missing/empty metrics;
- invalid aggregation/operation;
- duplicate synonyms across metrics;
- unsafe identifiers;
- unknown table and column through schema validation;
- invalid/unknown filter references and values;
- unknown profile fields.

### Runtime tests

- three personal metrics compile and execute;
- personal filter values remain bound params;
- injection-shaped filter values fail closed;
- unknown metric and unsupported query fail before SQL;
- explain never calls an executor;
- CLI returns concise actionable errors.

### MySQL tests

- personal profile/schema validation succeeds against the disposable service;
- personal SELECT queries succeed;
- runtime grants remain only USAGE + SELECT;
- direct INSERT/UPDATE/DELETE remain denied;
- existing demo MySQL integration continues to pass.

### Regression tests

- Project 03 ordinary suite;
- Project 00 integration suite and fixed Eval Set hash;
- 56-case Benchmark exactly 53/56;
- safety classification exactly 3/0/0/0;
- root Acceptance Gate and hosted GitHub Actions.

## 11. Acceptance Criteria

### Stable v1

- Eval Set byte hash unchanged.
- 56 cases, 53/56.
- `SAFE_FAILURE=3`, `FALSE_SUCCESS=0`, `UNSAFE_ALLOW=0`, `OVER_BLOCK=0`.
- Regression Gate and Safety Gate pass.

### Personal-use MVP

- A non-demo expenses profile is created without editing Core Engine code.
- At least three metrics and one filter work on SQLite test data and real
  disposable MySQL.
- Static and MySQL schema validation catch missing table/column errors.
- Filter parameters are bound and injection-shaped values are rejected.
- Explain mode performs no execution.
- The MySQL runtime identity is non-root and SELECT-only; SELECT succeeds and
  INSERT/UPDATE/DELETE are denied.
- Documentation lets the user onboard a database from a clean checkout.
- Local Acceptance Gate and hosted GitHub Actions pass.
- Final worktree is clean.

## 12. Release Decision

There is no unresolved architectural decision that requires expanding scope.
The format/contract/compiler details are fixed in
`PERSONAL_USE_V2_DESIGN.md`. MVP implementation may proceed incrementally.

The release label is `V2 MVP DONE` only after every acceptance criterion has
direct execution evidence. Otherwise it remains `PARTIAL` or `BLOCKED`.
