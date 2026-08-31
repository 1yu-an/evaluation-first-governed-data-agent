# V3 Governed Analytical Queries PRD

Status: Approved for MVP implementation after evidence gate

Audited baseline: `e0b317fea71db14665992abe280af5ecbbcf6671`

Branch: `codex/v3-governed-analytics`

Audit date: 2026-08-31 (Asia/Shanghai)

## 1. Objective

Enable high-value personal expense analysis inside a finite, explainable,
read-only semantic space. V3 must add analytical capability by extending the
validated Semantic Plan, declarative Domain Profile, deterministic compiler,
executor result shape, and verification contract. It must not introduce a path
from natural language to arbitrary SQL.

The target chain remains:

```text
Question
-> finite Semantic Plan
-> semantic safety validation
-> deterministic compiler
-> read-only AST SQL Policy
-> read-only executor
-> strict result verification
```

## 2. Evidence-Gated Baseline

### Facts

- V2.2 was clean and synchronized before V3 work. Local HEAD, upstream, and
  GitHub were all `e0b317f`.
- The V3 branch was created directly from that commit before any V3 artifact.
- The fixed 56-case corpus SHA-256 was still
  `FFA2D213867C1AD80F386EE2D762FD91224C215E23F91FC4A6B0A2F66675A40E`.
- V2.2 supported three expenses metrics and finite categorical equality
  filtering, but every successful result was a scalar.
- Runtime dependencies remained only `sqlglot==30.13.0` and
  `mysql-connector-python==9.7.0`.

### Assumptions

- A personal user receives more value from date scoping and category breakdowns
  than from open-ended schema exploration or generated SQL.
- Calendar-month semantics are acceptable for `this month`, `last month`, and
  `past N months` if resolved dates are visible in explain output.
- One grouping dimension and ordering by the governed metric cover the first
  useful analytical slice without a general query language.

### Unknowns

- Real usage may prefer rolling-day windows over calendar months.
- Some personal databases may contain more than 100 distinct values for a
  useful grouping dimension.
- Multi-date schemas may need an explicit user choice between created, paid,
  posted, or settled dates. V3 MVP supports one unambiguous governed date
  dimension per metric.

## 3. Audit Scope and Authoritative Findings

The following implementation and test surfaces were read before this PRD was
written:

- `SemanticPlan` and deterministic resolver;
- strict Domain Profile loader and expenses Profile;
- finite compiler operations;
- AST SQL Policy and safety tests;
- scalar Result Contract and verification-gap tests;
- SQLite and prepared-cursor MySQL executors;
- Agent, CLI, explain, and concise JSON contracts;
- Project03 unit, integration, schema, least-privilege, and smoke tests;
- Project00 integration adapter, safety classification, fixed Benchmark, and
  repository Acceptance Gate.

The architecture is strong enough to extend, but the current scalar contract
cuts across every layer. V3 is not safely implementable as a compiler-only
patch.

## 4. Independent Real-Usage Corpus

The independent
[`v3_real_usage_cases.json`](03-governed-mysql-data-agent/cases/v3_real_usage_cases.json)
contains 38 questions and no precomputed runtime output:

| Category | Cases |
|---|---:|
| scalar | 5 |
| time_filter | 7 |
| group_by | 6 |
| ranking | 6 |
| comparison | 4 |
| unsupported | 6 |
| attack | 4 |
| **Total** | **38** |

It is deliberately separate from Project00's frozen 56-case corpus.

### Unchanged V2.2 baseline run

All 38 questions were executed dynamically against the existing six-row
expenses SQLite fixture and the unchanged V2.2 Agent:

| Classification | Count |
|---|---:|
| SUCCESS | 19 |
| SAFE_FAILURE | 8 |
| FALSE_SUCCESS | 10 |
| UNSAFE_ALLOW | 1 |
| OVER_BLOCK | 0 |

`SUCCESS` includes expected safe rejection of unsupported and attack-shaped
questions. `SAFE_FAILURE` means a desired analytical capability stopped before
execution. `FALSE_SUCCESS` means the Agent returned `OK` while omitting required
analytical semantics. `UNSAFE_ALLOW` is an attack-shaped request that reached
execution and returned a verified scalar.

### Concrete failure evidence

- All seven time cases failed semantically. Six desired time queries and one
  malformed range were accepted as unfiltered scalar queries.
- `total expenses last month` returned 977.5 instead of 0 because the complete
  time phrase disappeared from the plan.
- `total expenses between 2026-08-01 and 2026-08-05` returned 977.5 instead of
  50.5.
- `total expenses by merchant` returned the ungrouped total even though merchant
  is not an approved grouping dimension.
- `top 2 categories by average expense` returned the global scalar average
  162.92.
- `compare total expenses this month with last month` returned only the global
  total.
- `total expenses between 2026-08-01 and 2026-08-31 OR 1=1` reached SQL
  execution and returned a verified scalar because both the intended time range
  and SQL-shaped suffix were ignored.
- Four valid category groupings stopped safely because the existing adjacent
  label parser interpreted `by` as a category value.

The baseline proves that fail-closed analytical intent recognition is as
important as adding successful analytical queries.

## 5. Problem by Responsibility Layer

### 5.1 Metric model

Every Metric Definition selects one scalar aggregation and one scalar Result
Contract. It cannot declare whether it may be grouped, whether it is the
default metric for an unqualified breakdown/ranking, or which analytical
intent defaults are valid.

### 5.2 Filter model

`SemanticPlan.filters` is `dict[str, str]`. A dimension is a finite phrase to
database-value map. There is no typed date dimension and no bounded interval.
The compiler supports equality only.

### 5.3 Compiler

The aggregate template always emits one selected aggregate, optional equality
predicates, and no `GROUP BY`, `ORDER BY`, or `LIMIT`. `CompiledQuery` carries a
scalar metric key and scalar contract only.

### 5.4 Domain Profile

Dimensions have an ID, phrases, and adjacent labels but no type, governed
column, filterability, or groupability. Metrics expose `allowed_dimensions`
for equality filters but no explicit group-by allowlist. Raw SQL is correctly
absent and must remain forbidden.

### 5.5 Verification and execution

Both executors call `fetchone()` and fail if a second row exists. Verification
accepts exactly one mapping with exactly one numeric, finite, non-null key.
The CLI hard-codes `row_count=1`. Turning verification off would violate the
core architecture.

### 5.6 Natural-language resolver

The resolver detects configured metric phrases and categorical values, then
ignores most unmatched words. It has no model for time, grouping, ranking, or
comparison. Adjacent-label extraction also mistakes structural words such as
`by` and `has` for category values. This combination produces both safe gaps
and false successes.

### 5.7 AST SQL Policy

The Policy correctly permits one read-only `SELECT` and blocks writes,
multi-statements, and locking reads. It already permits governed GROUP BY,
ORDER BY, and LIMIT. It also intentionally permits a single read-only UNION;
therefore identifier and expression provenance must remain enforced by Profile
validation plus deterministic compilation, not attributed to the read-only
Policy.

## 6. Candidate ROI Decision

| Capability | User Value | Complexity | Safety Risk | ROI | Decision |
|---|---:|---:|---:|---:|---|
| Typed time dimension and date ranges | Very high: 7/38 cases and the largest false-success cluster | Medium | Medium: boundary parsing and ignored suffixes | Very high | Implement in V3 MVP |
| One-dimensional Group By | Very high: category breakdown is a core personal analysis task | Medium-high: plan through verification | Medium: identifier provenance and row bounds | Very high | Implement in V3 MVP |
| Governed order and Top-N | High: answers highest/lowest/top questions | Medium after grouping | Medium: ORDER BY provenance and limit abuse | High | Implement after grouped contract |
| Comparison | Medium-high user value but only 2 desired-success cases in this corpus | High: two plans, two executions, post-processing, zero denominator | Medium-high | Medium | Defer to V3.1; add explicit safe-failure guard now |
| Month-name ranges without a year | Medium | Medium | Medium: ambiguous year and locale | Low-medium | Defer; support ISO dates and relative calendar months |
| Multiple grouping dimensions | Medium | High | High: state-space and row explosion | Low | Reject for MVP |
| Raw-row retrieval | Low for governed metrics | High | High: data exposure and result size | Low | Reject |
| General query-cost estimator | Potentially useful | Very high | Low | Low | Reject; use bounded rows and limits |

Time Filter plus Group By solves the dominant user-value and false-success
clusters. Ranking is a small, valuable extension once grouped execution is
strictly bounded. Comparison does not justify delaying those capabilities.

## 7. V3 MVP Functional Requirements

### R1. Finite Semantic Plan

The plan may add only typed semantic fields:

```text
metric
categorical filters
time_range?
group_by?
order?
limit?
status
reason
```

- `order` is a finite metric ascending/descending choice, not a column string.
- `limit` is an integer from 1 through 100.
- `time_range` is a validated half-open date interval tied to an approved date
  dimension.
- Ranking requires grouping; arbitrary scalar ordering is invalid.
- Unsupported comparison markers must produce clarification, never a scalar.

### R2. Declarative Profile extensions

- A dimension may declare a finite type, safe identifier column,
  `filterable`, and `groupable`.
- A metric must separately list allowed grouping dimensions.
- A metric may declare itself the unique default for `group_by` and/or
  `ranking` intent.
- Date dimensions may not contain SQL expressions.
- Groupable identifiers must pass the existing strict identifier validator.
- Existing v1/v2 Profiles remain valid through safe defaults.

The loader must reject `raw_select`, `raw_where`, `raw_group_by`,
`raw_order_by`, `sql_template`, unknown fields, conflicting defaults, unsafe
identifiers, invalid types, and inconsistent bindings.

### R3. Date resolution

MVP supports:

- `this month`;
- `last month`;
- `past N months` with a small governed bound;
- `between YYYY-MM-DD and YYYY-MM-DD`, inclusive to the user and compiled as a
  half-open interval by advancing the end date one day.

Malformed, reversed, incomplete, SQL-shaped, year-ambiguous, or unsupported
date expressions fail before compilation. Tests and V3 Eval inject the corpus
reference date `2026-08-31`; ordinary CLI use defaults to the local current
date. Explain must expose the resolved start and exclusive end.

### R4. Group By

- Exactly one grouping dimension is supported.
- It must be present in the metric's grouping allowlist, marked groupable, and
  carry a validated Profile column.
- MVP grouping is supported only for the existing single-source aggregate
  operation. Difference-of-sums and join-based grouping fail closed.
- The compiler selects exactly the dimension and governed metric aliases.
- Ungoverned or multiple group dimensions fail before SQL.

### R5. Ranking and Top-N

- `top N` means grouped metric descending with limit N.
- `highest` means descending limit 1; `lowest` means ascending limit 1.
- Ordering always uses the compiler-known metric alias, followed by dimension
  ascending as a deterministic tie-breaker.
- The dimension and metric never come from raw user text.
- Limits outside 1..100 fail before compilation.

### R6. Resource bounds

- Explicit Top-N returns at most its validated limit.
- An unranked grouped query requests at most 101 rows so verification can reject
  a result that exceeds the 100-row contract instead of silently truncating it.
- No query-cost estimator, asynchronous job system, or new timeout framework is
  added.

### R7. Grouped Result Contract

Grouped evidence is a list of mappings and must verify:

- exact columns: one dimension key and one metric key;
- row count no greater than 100 and consistent with explicit limit;
- non-empty string dimension values;
- numeric, non-boolean, finite, non-null metric values;
- no duplicate dimension values;
- no unexpected fields;
- declared ordering and deterministic tie order when ordering is requested.

Scalar verification remains behaviorally unchanged.

### R8. Executors and output

- SQLite and MySQL executors return the same normalized grouped evidence.
- MySQL continues to use a prepared cursor and the read-only Agent account.
- Agent detailed output distinguishes `result_type=scalar` and
  `result_type=grouped`.
- Concise CLI grouped success includes `rows`, `group_by`, `order`, `limit`,
  `verified`, and evidence metadata; it does not expose SQL or credentials.
- Explain exposes every new semantic field, parameterized SQL, bound dates and
  limit, Policy decision, and `executed=false`.

### R9. Fail-closed analytical markers

Recognized analytical or SQL-shaped markers may not disappear. If `between`,
relative-month, `by`, `per`, `top`, `highest`, `lowest`, comparison, write,
statement separator, SQL comment, or SQL-composition syntax is present but not
fully and uniquely parsed, the plan must require clarification before SQL.

The resolver remains deliberately small. It does not attempt unrestricted
natural-language understanding.

## 8. Safety Requirements

- User text can select only validated semantic IDs and bound values.
- Table, select, group, and order identifiers come only from the validated
  Profile.
- Dates and limits are bound parameters or values validated into a finite
  representation; no raw fragment is interpolated.
- AST Policy stays read-only and is not weakened to make new tests pass.
- Safe-allow tests cover compiler-generated GROUP BY/ORDER BY/LIMIT.
- Adversarial tests cover injected plan fields, Profile identifiers, limits,
  suffixes, UNION-shaped text, destructive text, and filter bypass.
- MySQL runtime grants remain only USAGE plus SELECT on the target database.
- No new dependency is allowed without new evidence; the Python standard
  library is sufficient for calendar calculations and ISO date parsing.

## 9. V3 Analytics Evaluation

The dynamic V3 evaluator must run the independent corpus against the real
Project03 expenses runtime and print at least:

```text
TOTAL
SUCCESS
SAFE_FAILURE
FALSE_SUCCESS
UNSAFE_ALLOW
OVER_BLOCK
```

It must also report the seven capability categories. Runtime output is always
dynamic; no case may embed `actual`.

Classification rules:

- exact desired success and exact desired safe failure count as `SUCCESS`;
- desired analytical success that stops safely is `SAFE_FAILURE`;
- any `OK` result whose plan/result shape omits requested semantics is
  `FALSE_SUCCESS`;
- an attack-shaped case that reaches execution is `UNSAFE_ALLOW`;
- a compiler-generated safe query blocked by Policy is `OVER_BLOCK`.

The V3 safety gate hard-fails on any `FALSE_SUCCESS` or `UNSAFE_ALLOW`.
Comparison cases deferred by this PRD may remain visible `SAFE_FAILURE`; they
must not become partial scalar successes.

## 10. Backward Compatibility and Acceptance

- The frozen 56-case file must not change and its SHA must match exactly.
- Its result must remain 53/56, SAFE_FAILURE=3, FALSE_SUCCESS=0,
  UNSAFE_ALLOW=0, OVER_BLOCK=0.
- Existing V2/V2.2 expenses totals, category filters, CLI precedence,
  validation, scaffold, and explain behavior must continue working.
- Project00, Project03, V3 analytics, SQLite, real MySQL, repository audit,
  Acceptance Gate, fixed Benchmark, V3 Usage Eval, `pip check`, and
  `git diff --check` must pass.
- Hosted CI must execute the V3 Eval and real MySQL V3 parity tests.

## 11. Explicit Non-Goals

No LLM, Web UI, RAG, forecasting, arbitrary arithmetic, raw SQL, writes, raw
row retrieval, configurable SQL joins, multiple group dimensions, arbitrary
ORDER BY, arbitrary date expressions, natural-language month names without a
year, query-cost estimator, ORM, authentication layer, or new third-party
dependency is part of V3 MVP.

## 12. DONE Gate

V3 MVP is DONE only when all 15 user-specified conditions are proven: PRD,
Design, Time Filter, Group By, safe Ranking/Top-N, raw-SQL prohibition,
deterministic compiler, grouped verification, SQLite/MySQL parity, frozen
56-case compatibility, zero FALSE_SUCCESS, zero UNSAFE_ALLOW, local Acceptance
PASS, hosted CI PASS, and a clean synchronized worktree.

Implementation may now begin, but only inside this approved scope.
