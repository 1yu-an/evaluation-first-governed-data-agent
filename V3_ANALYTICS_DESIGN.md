# V3 Governed Analytical Queries Design

Status: Implementation design approved by the V3 PRD gate

Baseline: `e0b317fea71db14665992abe280af5ecbbcf6671`

## 1. Design Goals

V3 adds time filtering, one-dimensional grouping, and metric ranking without
adding a query language. Every executable state is representable by a small
typed plan and every SQL token is generated from validated code or Profile
identifiers.

The design preserves three separate responsibilities:

```text
Resolver/Profile validation  prove semantic selections are governed
Compiler                     generate the only executable SQL shape
AST Policy                   prove the generated statement is one read-only query
```

The AST Policy is not misrepresented as a column/table provenance checker.

## 2. Target Architecture

```text
Question + reference date
        |
        v
Deterministic analytics resolver
  - reject SQL/write/comparison suffixes
  - resolve metric and categorical filters
  - resolve one date interval
  - resolve one group dimension
  - resolve finite metric order and bounded limit
        |
        v
Frozen SemanticPlan
        |
        v
Profile/plan consistency validation
        |
        v
Finite aggregate compiler
  - scalar template
  - grouped template
  - bound equality/date/limit parameters
        |
        v
sqlglot read-only AST Policy
        |
        v
SQLite / prepared MySQL executor
  - scalar mapping OR bounded grouped row list
        |
        v
ScalarResult / GroupedResult verification
        |
        v
Detailed Agent result -> concise CLI JSON -> V3 dynamic evaluator
```

## 3. Semantic Model

### 3.1 DateRange

```python
@dataclass(frozen=True)
class DateRange:
    dimension: str
    start_inclusive: date
    end_exclusive: date
    label: str
```

- The interval is always non-empty and half-open.
- `label` is a finite diagnostic label such as `this_month`, `last_month`,
  `past_3_months`, or `explicit_range`; it is not SQL.
- `to_dict()` serializes dates as ISO strings for explain and JSON.

### 3.2 SemanticPlan

```python
@dataclass(frozen=True)
class SemanticPlan:
    metric: str | None
    filters: dict[str, str]
    time_range: DateRange | None
    group_by: str | None
    order: str | None
    limit: int | None
    status: str
    reason: str
```

Allowed order values are constants:

```text
metric_asc
metric_desc
```

Invariants enforced before compilation:

- order implies group_by;
- limit implies group_by and order;
- group_by names exactly one Profile dimension;
- 1 <= limit <= 100;
- time_range names a Profile date dimension allowed by the metric;
- comparison intent never produces READY in V3 MVP.

Existing callers constructing a scalar plan receive explicit default values of
`None` for the new fields so v1/v2 behavior remains source-compatible.

## 4. Domain Profile Model

### 4.1 Dimension extension

Existing dimension objects accept these optional declarative fields:

```json
{
  "id": "category",
  "type": "categorical",
  "column": "category",
  "filterable": true,
  "groupable": true,
  "phrases": {"groceries": "food"},
  "adjacent_labels": ["category"]
}
```

The V3 date dimension is:

```json
{
  "id": "date",
  "type": "date",
  "column": "spent_on",
  "filterable": true,
  "groupable": false,
  "phrases": {},
  "adjacent_labels": ["date"]
}
```

Compatibility defaults are:

```text
type=categorical
column=null
filterable=true
groupable=false
```

Validation rules:

- type is only `categorical` or `date`;
- column is null or a safe identifier;
- groupable requires a non-null column and categorical type;
- date requires a non-null column, filterable=true, groupable=false, and no
  finite database-value phrases;
- categorical phrase values remain restricted by the existing fixed-literal
  validator;
- raw SQL-like fields remain unknown and invalid.

### 4.2 Metric extension

Each metric accepts two optional fields:

```json
{
  "allowed_group_by": ["category"],
  "default_intents": ["group_by", "ranking"]
}
```

Validation rules:

- allowed group dimensions exist, are groupable, and have safe columns;
- grouped MVP metrics use `AggregateOperation`, not difference-of-sums;
- the operation's binding column for a groupable dimension matches the
  dimension column;
- default intents are only `group_by` and `ranking`;
- at most one metric per Profile owns each default intent;
- a default metric must support at least one grouped dimension.

The expenses metrics add `date` to `allowed_dimensions` and a governed
`spent_on` filter binding. All three permit category grouping. Total expenses
is the Profile-declared default for unqualified grouping and ranking.

No table, column, expression, predicate, group, order, or template SQL can be
supplied outside the validated identifier/value fields already described.

## 5. Deterministic Resolution

Resolution uses a fixed stage order so one stage cannot silently consume text
belonging to another:

1. Normalize tokens without losing the original string.
2. Reject statement separators, SQL comments, SQL-composition phrases, and
   write/mutation intent.
3. Detect comparison markers and return explicit V3.1 clarification.
4. Parse one grouping expression (`by`, `per`, or `each` plus a Profile
   dimension label). Unknown or multiple group labels fail.
5. Parse ranking:
   - `top N` -> metric_desc plus N;
   - `highest` -> metric_desc plus 1;
   - `lowest` -> metric_asc plus 1.
6. Parse one time expression using the selected metric's unambiguous approved
   date dimension.
7. Parse categorical values. Structural tokens such as `by`, `has`, `each`,
   `per`, `top`, and `and` are forbidden as adjacent-label values.
8. Resolve explicit metric evidence. If none exists for a valid group/ranking
   intent, use the unique Profile-declared default for that intent.
9. Apply existing Profile guard rules and final completeness checks.

Any recognized analytics marker that remains incomplete causes
`NEED_CLARIFICATION`. Unknown ordinary filler is tolerated only when it cannot
change metric, filter, time, group, rank, comparison, or safety semantics.

### 5.1 Calendar algorithms

Only Python standard-library `date` and `calendar` behavior is used.

- this month: first day of the reference month through first day of next month;
- last month: first day of prior month through first day of reference month;
- past N months: first day of the oldest included calendar month through first
  day after the reference month;
- explicit range: parsed ISO start through parsed ISO end plus one day.

`past N months` uses a governed positive bound. Overflow, invalid dates,
reversed dates, duplicate ranges, and incomplete ranges fail closed.

The resolver accepts an optional `reference_date`. `DataAgent` stores and
passes it; CLI omission uses `date.today()`. Tests and V3 Eval pass
`2026-08-31` explicitly.

## 6. Compiler Design

### 6.1 Scalar time filter

```sql
SELECT ROUND(COALESCE(SUM(amount),0),2) AS total_expenses
FROM expenses
WHERE spent_on>=? AND spent_on<?
```

Parameters are ISO start and exclusive-end dates. Existing categorical and
fixed predicates compose with `AND` in deterministic field order.

### 6.2 Unranked grouped query

```sql
SELECT category AS category,
       ROUND(COALESCE(SUM(amount),0),2) AS total_expenses
FROM expenses
WHERE spent_on>=? AND spent_on<?
GROUP BY category
ORDER BY category ASC
LIMIT ?
```

The compiler binds 101 as the internal limit. Verification rejects 101 rows,
proving the 100-row contract instead of presenting silent truncation.

### 6.3 Ranked grouped query

```sql
SELECT category AS category,
       ROUND(COALESCE(SUM(amount),0),2) AS total_expenses
FROM expenses
GROUP BY category
ORDER BY total_expenses DESC, category ASC
LIMIT ?
```

The bound limit has already passed the Semantic Plan 1..100 invariant.

### 6.4 Compiler provenance checks

- source table and aggregate column come from `AggregateOperation`;
- group column comes from the Profile dimension and must equal the operation
  binding declared for that metric;
- metric alias comes from the validated metric ID;
- order expression is generated from the result alias constant;
- no user string is accepted for select, group, or order fields;
- `CompiledQuery` carries the exact Result Contract matching its mode.

## 7. Result Contracts and Verification

### 7.1 Compatibility shape

`ResultContract.scalar_numeric()` is unchanged. The contract gains an explicit
mode plus optional grouped metadata without changing existing scalar behavior.

### 7.2 Grouped contract

```python
ResultContract.grouped_numeric(
    expected_key="total_expenses",
    dimension_key="category",
    max_rows=100,
    requested_limit=3,
    order="metric_desc",
)
```

Grouped verification accepts only a list of mappings. It checks:

1. list shape;
2. row count <= max_rows and <= requested_limit when present;
3. exact key set `{dimension_key, expected_key}` per row;
4. dimension is a non-empty string and not duplicated;
5. metric is numeric, non-boolean, finite, and non-null;
6. metric monotonicity for metric order;
7. dimension ascending for equal metric values;
8. dimension ascending for the unranked deterministic order.

Zero grouped rows are valid and verify as an empty list. This differs from a
scalar AVG/MAX null, which continues to fail its non-null scalar contract.

## 8. Executor Design

`QueryExecutor.execute()` returns either:

```text
dict[str, value]             scalar
list[dict[str, value]]       grouped
```

The mode comes only from the compiled contract.

- Scalar uses the existing one-row/two-fetch enforcement.
- Grouped reads at most the compiler-bounded result, maps exact cursor column
  names, normalizes MySQL Decimal values, and does not truncate before
  verification.
- SQLite row mappings and MySQL prepared rows are normalized to the same list
  shape.
- Connection/cursor cleanup and explicit execution errors remain unchanged.

## 9. Agent, Explain, and CLI

### 9.1 Detailed Agent output

Scalar success preserves the existing `value` and evidence mapping.

Grouped success adds:

```json
{
  "status": "OK",
  "result_type": "grouped",
  "metric": "total_expenses",
  "group_by": "category",
  "order": "metric_desc",
  "limit": 3,
  "rows": [
    {"category": "housing", "total_expenses": 900.0}
  ],
  "verified": true
}
```

The trace remains resolve -> compile -> policy -> execute -> verify.

### 9.2 Explain

Explain includes serialized `time_range`, group, order, limit, SQL, bound
params, contract mode, and `executed=false`. It never initializes an executor.

### 9.3 Concise CLI

Grouped ask output includes profile, metric, filters, time range, group, order,
limit, rows, verified, and evidence metadata containing row count and exact
column names. SQL, DSNs, credentials, and trace remain absent.

Failure reason codes add finite analytical categories:
`invalid_time_filter`, `unsupported_grouping`, `invalid_ranking`,
`unsupported_comparison`, and `unsafe_input`, without changing existing
V2.2 codes.

## 10. AST Policy Position

No Policy relaxation is planned because the current parser already allows
read-only GROUP BY, ORDER BY, and LIMIT. Tests will prove:

- each compiler-generated analytical shape is allowed;
- multi-statements, writes, and locking reads stay blocked;
- query-text injection never reaches compilation;
- malicious plan/profile identifiers fail before SQL;
- the existing documented read-only UNION behavior remains compatible.

If actual compiler SQL is unexpectedly blocked, any Policy change requires a
new AST safety argument and adversarial tests. Passing a test alone is not a
reason to change Policy.

## 11. V3 Dynamic Evaluation

Project00 receives a narrow V3 adapter and benchmark command rather than a new
general framework.

```text
Project03 cases/v3_real_usage_cases.json
-> Project00 GovernedExpensesRuntime
-> real DataAgent + expenses Profile + injected reference date
-> dedicated Project00 V3 expectation/safety classifier
-> V3 outcome and capability summary
```

Successful scalar/grouped cases require exact expected state, Policy allow,
strict verification, and the full ordered trace. Expected clarifications
forbid SQL, evidence, execution, and verified success. Desired comparison
successes that remain safe clarifications are classified `SAFE_FAILURE`, not
hidden as successes.

The command prints the required totals and category rows, can optionally write
a deterministic JSON report, and exits nonzero when its declarative gate is
violated. The repository Acceptance Gate adds this command as a required
check. The existing Project03 integration adapter, fixed cases, reports, and
thresholds remain unchanged.

## 12. Test Matrix

### Semantic Plan

- valid this/last/past/explicit range;
- malformed, reversed, duplicate, incomplete, and SQL-shaped range;
- valid group-by and Profile default metric;
- invalid/unknown/multiple group dimension;
- valid top/highest/lowest;
- zero, negative, excessive, nonnumeric, and injection-shaped limit;
- comparison markers fail before SQL.

### Profile and compiler

- safe V3 Profile fields load immutably;
- unknown/raw SQL fields and unsafe columns fail;
- invalid types/default ownership/bindings fail;
- scalar time predicates are bound;
- grouped select/group/order identifiers are Profile-derived;
- internal 101 and explicit Top-N limits are bound;
- injected plan IDs and values fail closed.

### Policy

- compiler-generated time/group/rank SQL allowed;
- destructive, multi-statement, and locking SQL blocked;
- existing safe read-only behavior preserved.

### Verification and executors

- valid scalar unchanged;
- valid grouped, empty grouped, and both database numeric representations;
- wrong columns, extra columns, wrong dimension/metric types, duplicate
  dimensions, excessive rows, excess explicit limit, non-finite values, and
  incorrect ordering fail;
- SQLite and MySQL return identical normalized rows.

### End to end and evaluation

- total expenses this month;
- total expenses between two ISO dates;
- expenses by category;
- top 3 expense categories;
- highest and lowest category;
- unsupported grouping and comparison safe failures;
- all attack corpus cases stop before execution;
- V3 summary fields and safety exit behavior;
- fixed 56-case SHA and 53/56 result unchanged.

## 13. Implementation Sequence

```text
Profile types and validation
-> DateRange and finite plan invariants
-> deterministic time/group/rank resolver
-> grouped Result Contract
-> finite compiler templates
-> bounded SQLite/MySQL execution
-> Agent/CLI/explain output
-> V3 dynamic evaluator
-> real MySQL parity
-> full regression and hosted CI
```

Comparison remains a visible, measured safe failure for V3 MVP. Its future
design must use two governed scalar plans plus deterministic post-processing;
it may not enter the current compiler as arbitrary arithmetic.
