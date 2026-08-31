# V3 Governed Analytical Queries Report

Status: V3 MVP accepted

Date: 2026-08-31 (Asia/Shanghai)

Baseline: `e0b317fea71db14665992abe280af5ecbbcf6671`

Implementation: `e57ebeaba197f7396aeaf17c10d562fb2951bced`

## A. Problem

V2.2 could answer governed scalar expense metrics and finite categorical
equality filters, but analytical modifiers were not represented in its plan.
An unchanged V2.2 run over the new 38-question real-usage corpus produced:

| Outcome | Count |
|---|---:|
| SUCCESS | 19 |
| SAFE_FAILURE | 8 |
| FALSE_SUCCESS | 10 |
| UNSAFE_ALLOW | 1 |
| OVER_BLOCK | 0 |

All seven time cases were semantically wrong. For example, last-month expense
returned the global 977.5 instead of 0, and the inclusive 2026-08-01..05
range returned 977.5 instead of 50.5. Grouping, ranking, and comparison
markers could disappear and leave a verified scalar. A range followed by
`OR 1=1` also reached execution because both the range and suffix were
ignored. The root cause crossed every responsibility layer: scalar-only
metrics and filters, no Profile date/group declarations, scalar-only compiler
and executors, scalar verification, and a resolver that tolerated unmatched
analytical structure.

## B. PRD Decisions

The PRD ranked typed time range and one-dimensional Group By as the highest
ROI gaps. Ranking/Top-N was selected as a small bounded extension after
grouping. Comparison was deferred to V3.1 because it needs two governed plans,
two executions, deterministic post-processing, and zero-denominator rules.

| Capability | Decision |
|---|---|
| Time dimension and date range | Implement |
| One Profile-approved Group By | Implement |
| Metric order and Top-N, max 100 | Implement |
| Comparison | Explicit safe failure; defer to V3.1 |
| LLM, arbitrary SQL, forecasting, writes, raw rows | Reject |

No third-party dependency was added; Python standard-library dates were
enough.

## C. Architecture Changes

The governed chain remains:

    Question
    -> immutable declarative Profile
    -> finite SemanticPlan
    -> compiler consistency validation
    -> deterministic SQL compiler
    -> unchanged read-only AST Policy
    -> SQLite / prepared MySQL executor
    -> scalar or grouped verification
    -> Agent / CLI / independent V3 Eval

`SemanticPlan` gained a typed half-open `DateRange`, one `group_by`, finite
metric order, and optional bounded limit. Profile dimensions gained
categorical/date type, approved column, filterability, and groupability.
Metrics gained explicit group allowlists and unique default analytical
intents. `DataAgent` accepts an injectable reference date for deterministic
tests and evaluation.

## D. New Query Capabilities

The expenses Profile now supports:

- this month, last month, past N calendar months, and inclusive ISO ranges;
- categorical equality composed with a date range;
- total, count, and average grouped by approved category;
- deterministic dimension order for ordinary groups;
- highest, lowest, and Top-N metric ranking with category tie order;
- grouped ask JSON and no-execution explain output.

Examples verified end to end include `total expenses this month`, `average
expense for the past 3 months`, `total expenses by category`, `top 3 expense
categories`, and `which category has the lowest total expenses?`.

## E. Safety Model

Profile configuration remains declarative and strict. Unknown fields such as
raw select/where/group/order/template SQL are invalid. Table and aggregate
columns come from validated operations; group columns must match an approved
dimension binding; order expressions are compiler constants. User dates and
limits are bound parameters after finite validation.

The AST Policy was not weakened. It already allows one read-only SELECT with
GROUP BY, ORDER BY, and LIMIT, while blocking writes, multiple statements,
and locking reads. Direct Policy tests cover both the governed allow shape and
a grouped `FOR UPDATE` rejection. SQL-shaped question suffixes and mutation
intent stop before compilation.

Resource bounds are explicit: Top-N is 1..100, grouped verification permits at
most 100 rows, and an unranked query binds 101 only as an overflow probe. The
MySQL Agent identity is separate from setup/admin and has only USAGE plus
SELECT on the target database.

## F. Verification Changes

Scalar verification remains exactly-one, exact key, non-null numeric, finite,
and non-boolean. The new grouped contract requires a list of mappings and
checks:

- exact dimension and metric columns with no extras;
- maximum rows and explicit requested limit;
- non-empty string and unique dimension values;
- numeric, non-boolean, finite metric values;
- dimension order or metric asc/desc order;
- deterministic dimension tie order.

Both executors retain one overflow row so excessive evidence fails
verification rather than appearing successfully truncated. MySQL Decimal
values are normalized before the same contract is applied.

## G. V3 Evaluation Results

The independent corpus contains 38 questions and no precomputed `actual`.
Project00 dynamically invokes the real Project03 expenses runtime at reference
date 2026-08-31.

| Outcome | Count |
|---|---:|
| TOTAL | 38 |
| SUCCESS | 36 |
| SAFE_FAILURE | 2 |
| FALSE_SUCCESS | 0 |
| UNSAFE_ALLOW | 0 |
| OVER_BLOCK | 0 |
| OTHER | 0 |

| Category | Total | Success | Safe failure |
|---|---:|---:|---:|
| scalar | 5 | 5 | 0 |
| time_filter | 7 | 7 | 0 |
| group_by | 6 | 6 | 0 |
| ranking | 6 | 6 | 0 |
| comparison | 4 | 2 | 2 |
| unsupported | 6 | 6 | 0 |
| attack | 4 | 4 | 0 |

The two safe failures are `v3-comparison-months` and
`v3-comparison-categories`, both deliberately deferred desired capabilities.
Expected comparison/unsupported/attack refusals count as successes only when
they stop without SQL, evidence, execution, or verified success.

## H. V1 Regression Results

The frozen Project00 integration file was not modified. Its SHA-256 remains:

    FFA2D213867C1AD80F386EE2D762FD91224C215E23F91FC4A6B0A2F66675A40E

The dynamic fixed result remains 53/56 with SAFE_FAILURE=3,
FALSE_SUCCESS=0, UNSAFE_ALLOW=0, OVER_BLOCK=0, and both Regression/Safety
gates passing. The three retained cases remain money made, turnover, and
fulfilled purchases.

## I. SQLite / MySQL Evidence

SQLite end-to-end tests cover time totals/count/average, grouped totals,
highest/lowest, average ranking, explain, CLI multirow output, overflow, and
safe failures.

A disposable local MySQL Community Server 8.0.46 instance on port 3307 was
initialized outside the existing Windows service. Repository setup created
the demo/expenses fixtures and a distinct `data_agent_ro` identity. Effective
grants were exactly USAGE plus SELECT on `data_agent`.*. The real suite passed
11/11, including SQLite/MySQL equality for time filter, Group By, and Top-N,
and direct UPDATE/INSERT/DELETE rejection. The instance was gracefully
stopped and its validated temporary directory removed.

Hosted CI independently provisioned MySQL 8.0.46 and passed the same
`acceptance_gate.py --with-mysql` path.

## J. Rejected Features

V3 does not implement comparison execution, percentage change, multiple group
dimensions, arbitrary date expressions, raw row retrieval, configurable SQL
joins, arbitrary arithmetic/order, forecasting, writes, LLM planning, RAG, or
a Web UI. Read-only UNION remains an AST Policy behavior, not a user semantic
building block; SQL provenance stays with Profile validation and compiler
templates.

## K. Remaining Limitations

The date resolver intentionally supports a small English pattern set and ISO
dates, not locale month names. Only one date range and one categorical group
are allowed. Scalar AVG/MAX over an empty range remains a non-null contract
failure. The six-row fixture proves deterministic parity, not production
query cost or broad language coverage. A 100-row bound is resource protection,
not a full cost estimator.

### Is the deterministic resolver now the next major bottleneck?

**NO, not on current evidence.** In the V3 corpus, every scalar, time_filter,
group_by, ranking, unsupported, and attack case meets its governed
expectation. The only two desired capabilities that fail are comparisons,
which lack an approved execution/post-processing model rather than a resolver
phrase.

The V2.2 baseline did expose resolver risks: four valid category groupings
were misread because `by` became a category value, and ten false successes
plus one unsafe allow involved ignored analytical/SQL-shaped markers. V3
fixed those concrete cases with structural-token guards and fail-closed
recognition. The resolver should be reconsidered as the primary bottleneck
only when a broader paraphrase corpus shows repeated failures for already
approved semantics, or when finite patterns become harder to audit than a
typed planner. Today the next product gap is governed comparison, followed by
broader usage evidence.

## L. Git / CI Evidence

Git history uses two implementation commits on
`codex/v3-governed-analytics` with no reset, rewrite, or force push:

- `aa8e770` — usage corpus, PRD, and Design;
- `e57ebea` — governed analytics implementation, tests, evaluator, gate, and
  documentation.

Local evidence:

| Check | Status | Evidence |
|---|---|---|
| Project00 | PASS | 62 passed |
| Project03 | PASS | 307 passed, 1 opt-in skip, 13 subtests |
| Real MySQL | PASS | 11 passed, USAGE + SELECT only |
| Repository audit | PASS | 17 tests; 0 findings |
| Fixed 56 Benchmark | PASS | 53/56 and safety invariants |
| V3 Analytics Gate | PASS | 36/38; zero false/unsafe/over-block |
| Full Acceptance with MySQL | PASS | FINAL RESULT: PASS |
| pip check | PASS | no broken requirements |
| git diff --check | PASS | no whitespace errors |

Hosted evidence:

- [CI Regression Gate run 33408286472](https://github.com/1yu-an/evaluation-first-governed-data-agent/actions/runs/33408286472)
  completed successfully for implementation commit `e57ebea`;
- the hosted job ran the disposable-MySQL setup and full real-MySQL
  Acceptance Gate.

At delivery, the report/current-state documentation is committed, the final
branch is synchronized with origin, and the worktree is clean.
