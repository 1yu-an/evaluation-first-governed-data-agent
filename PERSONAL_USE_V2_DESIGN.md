# v2 Personal-Use Data Agent Design

Status: Approved for MVP implementation  
Base: stable v1 at `5afe98c157d416a797b473c5bbea21c87cbdfdb0`  
Branch: `codex/v2-personal-use`  
Companion requirements: `PERSONAL_USE_V2_PRD.md`

## 1. Design Summary

v2 keeps the evaluated deterministic Core Engine and moves business-specific
knowledge into a validated external Domain Profile. A profile describes metric
language, finite filters, and a small set of safe aggregate query plans. It does
not contain arbitrary SQL.

The default profile exactly represents the v1 orders/payments/refunds domain,
so callers that do not select a profile retain the same public behavior and
benchmark results. A separate expenses profile proves that a user can connect a
different business schema without editing resolver or compiler source code.

The runtime flow is:

```text
JSON profile -> parse + static validate -> immutable DomainProfile
                                              |
question -> normalize -> resolve metric/filter -> SemanticPlan
                                              |
                         compile validated operation -> QueryPlan
                                              |
                         policy check -> read-only executor
                                              |
                         semantic verification -> answer contract
```

For MySQL, startup validation adds one step before questions are served:

```text
DomainProfile.required_schema
        +
INFORMATION_SCHEMA.COLUMNS snapshot
        |
compare tables/columns -> pass or actionable startup failure
```

## 2. First-Principles Boundary

### 2.1 What remains Core Engine

- profile parsing and validation mechanics;
- generic normalization and phrase matching;
- deterministic ambiguity handling;
- a finite aggregate compiler;
- SQL policy enforcement;
- SQLite/MySQL execution;
- semantic result verification;
- answer and error contracts;
- CLI orchestration.

### 2.2 What moves to Domain Profile

- metric identifiers, meanings, phrases, synonyms, and compositions;
- ambiguity/guard phrases that have domain meaning;
- dimension phrases and the finite mapping from user words to database values;
- each metric's allowed dimensions;
- table, column, join, and fixed-predicate metadata;
- result-key behavior used by legacy answers.

### 2.3 What is deliberately not configurable

- arbitrary SQL text, expressions, functions, subqueries, or operators;
- write operations;
- database credentials;
- runtime policy limits;
- Python import paths or executable hooks.

This boundary makes a profile useful to a personal user without turning it into
an alternate SQL execution channel.

## 3. Why JSON

JSON is selected for v2.

- It is parsed by the Python standard library, so the dependency surface does
  not grow.
- It has deterministic scalar types and rejects comments/tags/executable
  objects.
- Strict unknown-field validation is straightforward.
- The same document can be checked in tests, CI, and the CLI.

Python configuration was rejected because it executes code and still requires
source-level customization. YAML was rejected for this MVP because it adds a
parser dependency and additional scalar/parsing ambiguity without changing the
core value proposition. A later version may offer a YAML-to-JSON authoring
adapter while retaining this JSON runtime contract.

## 4. Profile Contract

### 4.1 Top-level object

```json
{
  "profile_version": 1,
  "id": "expenses",
  "description": "Personal expense analytics",
  "language": {},
  "dimensions": [],
  "metrics": []
}
```

Required top-level fields are `profile_version`, `id`, `language`,
`dimensions`, and `metrics`. `description` is optional. Version 1 is the only
accepted version. Unknown fields fail validation with a JSON path.

### 4.2 Identifiers and literals

Profile/database identifiers use:

```text
^[A-Za-z_][A-Za-z0-9_]*$
```

This applies to profile IDs, metric IDs, dimension IDs, result aliases, table
aliases, tables, and columns. Qualified names and quoting characters are not
accepted in the profile.

Fixed predicate values are strings matching:

```text
^[A-Za-z0-9_.-]+$
```

and fixed predicates support equality only. Question-derived values are always
bound parameters and never interpolated.

### 4.3 Language object

```json
{
  "token_normalization": {"orders": "order"},
  "scope_ambiguity_markers": ["across", "versus"],
  "guard_rules": [
    {
      "id": "refund_only",
      "reason": "refund-only meaning requires clarification",
      "all_features": ["refund"],
      "any_features": ["only"],
      "ignore_if_dimensions": []
    }
  ]
}
```

- `token_normalization` maps whole lower-case tokens to their normalized form.
- `scope_ambiguity_markers` are generic ambiguity markers used when multiple
  dimension values occur in one question.
- A guard rule is triggered when all `all_features` are present and, when
  non-empty, at least one `any_features` value is present.
- `ignore_if_dimensions` suppresses a rule only when the named dimension was
  explicitly extracted. This preserves the v1 distinction between conflicting
  state language and an explicit `status ...` filter that the compiler can
  reject precisely.

Phrases are trimmed, lower-cased, non-empty strings. Duplicates after
normalization fail validation.

### 4.4 Dimension object

```json
{
  "id": "category",
  "phrases": {
    "food": "food",
    "groceries": "food",
    "transport": "transport"
  },
  "adjacent_labels": []
}
```

Each key is a user-visible phrase and each value is the exact finite database
value. This is intentionally not an open-ended extracted value. Longest phrase
wins; equal-length phrases that map to different values are a validation error.
When a question contains more than one distinct value for a dimension, the
resolver returns `AMBIGUOUS` rather than silently choosing one.

`adjacent_labels` is an optional, finite list of labels such as `region`. For a
label `region`, the resolver may preserve the single normalized token in either
`<value> region` or `region <value>`. This supports an important fail-closed
case: `central region` must be represented in the semantic plan and rejected as
an unsupported value instead of being silently dropped. Adjacent extraction
does not make a value valid: only values present in `phrases` may compile, and
the value is still a bound parameter. Multi-token personal aliases such as
`groceries` remain explicit phrase mappings.

### 4.5 Metric language

```json
{
  "id": "total_expenses",
  "meaning": "Sum of recorded expense amounts",
  "canonical_forms": ["total expenses"],
  "synonyms": ["spending", "amount spent"],
  "composition_patterns": [],
  "allowed_dimensions": ["category"],
  "result_key": {"mode": "metric"},
  "operation": {}
}
```

`canonical_forms`, `synonyms`, and `composition_patterns` are all optional
matching evidence, but their combined phrase set must be non-empty.
A composition pattern is an ordered list of required phrases. It supports v1
concepts such as `completed` + `order` + `count` without embedding those words
in Core Engine.

Resolution remains deterministic:

1. normalize the question;
2. find exact phrase and composition evidence from every metric;
3. apply configured guard rules;
4. reject zero matches as `UNSUPPORTED`;
5. reject multiple surviving metrics as `AMBIGUOUS`;
6. resolve dimensions and enforce `allowed_dimensions`;
7. emit one `SemanticPlan`.

`result_key.mode` is one of:

- `metric`: result key is the metric ID;
- `dimension_value_prefix`: result key is
  `<resolved-value>_<configured-suffix>`.

The second mode exists only to preserve the stable v1 regional result keys.

### 4.6 Aggregate operation

The ordinary operation is:

```json
{
  "type": "aggregate",
  "aggregate": "sum",
  "source": {"table": "expenses", "alias": "e"},
  "column": "amount",
  "round_digits": 2,
  "coalesce_zero": true,
  "fixed_predicates": [],
  "filter_bindings": {
    "category": {"table_alias": "e", "column": "category"}
  }
}
```

Supported aggregates are `count`, `sum`, `avg`, and `max`.

- `count` requires `column` to be absent and compiles to `COUNT(*)`.
- `sum`, `avg`, and `max` require a column.
- `round_digits` is absent or an integer from 0 through 6.
- `coalesce_zero` is allowed for count/sum and defaults to false.
- `fixed_predicates` contain only validated alias, column, and fixed equality
  values.
- `filter_bindings` maps an allowed dimension to a validated alias/column.

The compiler constructs SQL exclusively from validated fields and fixed
templates. It uses the `?` qmark convention for both SQLite and MySQL because
Connector/Python prepared cursors accept native qmark markers; params remain a
separate tuple in both backends.

### 4.7 Difference-of-sums operation

The v1 revenue definition needs a small, explicit second operation:

```json
{
  "type": "difference_of_sums",
  "left": {
    "source": {"table": "payments", "alias": "p"},
    "column": "amount",
    "fixed_predicates": [
      {"table_alias": "p", "column": "status", "value": "completed"}
    ]
  },
  "right": {
    "source": {"table": "refunds", "alias": "r"},
    "column": "amount",
    "fixed_predicates": []
  },
  "round_digits": 2,
  "filter_joins": {
    "region": {
      "table": "orders",
      "alias": "o",
      "value_column": "region",
      "left_join": {
        "source_alias": "p",
        "source_column": "order_id",
        "target_column": "id"
      },
      "right_join": {
        "source_alias": "r",
        "source_column": "order_id",
        "target_column": "id"
      }
    }
  }
}
```

It compiles two independently filtered scalar `SUM` subqueries and subtracts
them. Each side is coalesced to zero. Filter values are bound once per side.
No generalized arithmetic expression language is introduced.

### 4.8 Required-schema derivation

The loader derives the required schema; the profile does not duplicate it.
Every table/column reference in sources, aggregates, predicates, bindings, and
joins is accumulated as:

```python
{
    "expenses": {"amount", "category"},
}
```

Aliases are resolved during validation. Duplicate aliases or references to an
unknown alias fail before schema derivation.

## 5. Python Model and Modules

### 5.1 New modules

`src/profile.py`

- frozen dataclasses for the objects above;
- `load_profile(path: Path | str) -> DomainProfile`;
- `load_default_profile() -> DomainProfile` with process-local immutable cache;
- `validate_profile_data(data, source) -> DomainProfile`;
- `ProfileValidationError` containing one or more path-qualified issues;
- `required_schema(profile) -> dict[str, frozenset[str]]`.

`src/schema_validation.py`

- `SchemaValidationError` with missing tables and columns;
- `validate_schema_snapshot(profile, snapshot)` for pure unit tests;
- `fetch_mysql_schema(connection, database)` using a fixed parameterized query
  against `INFORMATION_SCHEMA.COLUMNS`;
- `validate_mysql_schema(profile, connection, database)`.

The metadata query is constant application code:

```sql
SELECT TABLE_NAME, COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = %s
```

It does not use user/profile identifiers in the query text.

### 5.2 Changed modules

`src/catalog.py`

- becomes compatibility access around the default profile;
- contains no orders/payments/refunds catalog literals;
- retains stable names used by tests where practical.

`src/semantic.py`

- resolver accepts an optional `DomainProfile`;
- default is the cached demo profile;
- generic matching replaces demo-specific branches;
- `SemanticPlan` remains the boundary passed to the compiler.

`src/compiler.py`

- compiler accepts an optional profile;
- dispatches only to `aggregate` and `difference_of_sums` templates;
- contains no demo table/column/region constants;
- retains the shared prepared qmark placeholder contract.

`src/agent.py`

- constructor accepts `profile=None` or a loaded `DomainProfile`;
- `run()` passes the profile through resolve and compile;
- `explain()` stops after compile/policy and never calls the executor;
- stable v1 return fields remain; the new answer contract is additive.

`src/cli.py`

- adds subcommands while preserving the old positional-question invocation;
- loads explicit `--profile`, then `DATA_AGENT_PROFILE`, then default demo;
- reports validation/runtime errors without tracebacks in normal mode.

`scripts/setup_mysql.py`

- continues to provision the least-privilege account;
- also creates and seeds the expenses example table;
- never prints the password.

## 6. Files and Configuration

```text
03-data-agent-portfolio-phase/
  profiles/
    demo.json
    expenses.json
  sql/
    expenses_mysql.sql
  src/
    profile.py
    schema_validation.py
  tests/
    test_profile.py
    test_schema_validation.py
    test_personal_profile.py
```

The existing `.env` contract is unchanged:

- `DATA_AGENT_DB_BACKEND=mysql`
- `DATA_AGENT_MYSQL_HOST`
- `DATA_AGENT_MYSQL_PORT`
- `DATA_AGENT_MYSQL_DATABASE`
- `DATA_AGENT_MYSQL_USER`
- `DATA_AGENT_MYSQL_PASSWORD`
- optional `DATA_AGENT_PROFILE`

No credential appears in either profile.

## 7. CLI Contract

### 7.1 Compatibility mode

```powershell
python -m src.cli "revenue"
```

This is equivalent to `ask` with the default demo profile.

### 7.2 Ask

```powershell
python -m src.cli ask --profile profiles/expenses.json `
  "total expenses for groceries"
```

Normal output is concise JSON with no SQL:

```json
{
  "status": "success",
  "metric": "total_expenses",
  "filters": {"category": "food"},
  "value": 42.5,
  "verified": true,
  "evidence": {"row_count": 1, "result_key": "total_expenses"}
}
```

Failure output includes `status`, `reason`, and an empty `evidence` object. The
process exits non-zero for profile, schema, configuration, policy, execution,
and verification failures.

### 7.3 Explain

```powershell
python -m src.cli explain --profile profiles/expenses.json `
  "average expense for transport"
```

Explain output includes the selected profile/metric, resolved filters,
parameterized SQL, parameters, `parameter_style=qmark`, and policy decision.
It does not open a database connection or execute a query. A test injects an
executor that raises if called.

### 7.4 Validate

```powershell
python -m src.cli validate-profile --profile profiles/expenses.json
python -m src.cli validate-profile --profile profiles/expenses.json `
  --check-mysql-schema
```

The first command is offline. The second reads the configured MySQL metadata
and fails with missing `table.column` paths before any business query.

## 8. Answer and Error Contracts

### 8.1 Success

The stable v1 fields remain present. Additive fields expose:

- `status = success`;
- `profile_id`;
- `metric`;
- normalized `filters`;
- scalar `value`;
- `verified = true`;
- `evidence.row_count` and `evidence.result_key`.

SQL and bound parameters remain internal except in explain/debug output.

### 8.2 Safe failure

Failures use the existing stable reason values when applicable. New
configuration failures are classified as `CONFIG_ERROR` or `SCHEMA_MISMATCH`.
They never claim success and expose no fabricated evidence.

Profile validation messages list all discovered issues in stable path order,
for example:

```text
metrics[1].operation.column: unknown identifier syntax 'amount; DROP TABLE x'
metrics[2].allowed_dimensions[0]: unknown dimension 'team'
```

Schema errors use:

```text
SCHEMA_MISMATCH: missing table expenses; missing column payments.amount
```

## 9. Security Model

Security is enforced in independent layers:

1. JSON parsing accepts data, not code.
2. Strict validation rejects unknown keys/types, unsafe identifiers, invalid
   references, and unsupported operations.
3. The compiler has finite templates and binds question-derived values.
4. The existing SQL policy allows one read-only SELECT and rejects comments,
   multiple statements, writes, and disallowed constructs.
5. MySQL runs as the existing non-root `data_agent_reader` account with SELECT
   only.
6. Semantic verification checks the scalar shape and the expected result key.

Changing a profile cannot bypass layers 3 through 6. Database privilege is the
last line of defense even if application validation regresses.

## 10. Compatibility Strategy

`profiles/demo.json` is the only source of demo-domain metadata after migration.
Default arguments load it, so these remain compatible:

- `DataAgent()`;
- `resolve(question)`;
- `compile_plan(plan)`;
- `python -m src.cli "question"`;
- Project00 `integration_03.py`;
- the immutable 56-case Eval Set.

Compatibility is proven by:

- all existing Project03 unit tests;
- Project00 adapter tests;
- SHA-256 equality for the fixed Eval Set;
- exact benchmark distribution 53/56 and 3/0/0/0 safety counts.

If generic SQL formatting differs while behavior remains equivalent, unit tests
will assert the new deterministic representation. The fixed benchmark outcome,
policy behavior, and result contract may not change.

## 11. Expenses Example

Schema:

```sql
CREATE TABLE expenses (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    spent_on DATE NOT NULL,
    category VARCHAR(40) NOT NULL,
    merchant VARCHAR(100) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    note VARCHAR(255) NULL
);
```

Seed at least six rows across `food`, `transport`, and `housing`. The profile
defines:

- `total_expenses`: rounded/coalesced sum of `amount`;
- `expense_count`: count of rows;
- `average_expense`: rounded average of `amount`;
- `category`: finite aliases mapping to the three stored categories.

Acceptance questions include:

- `total expenses`;
- `how many expenses`;
- `average expense`;
- `total expenses for groceries`;
- an unsupported question;
- a multi-category ambiguous question;
- an injection-shaped category phrase that must not become SQL.

## 12. Validation and Test Matrix

### 12.1 Profile unit tests

- load demo and expenses profiles;
- reject malformed JSON and wrong version;
- reject missing and unknown fields;
- reject duplicate IDs/phrases/aliases;
- reject unsafe identifiers and fixed literals;
- reject broken metric/dimension/alias/join references;
- derive exact required schemas.

### 12.2 Resolver/compiler/runtime tests

- preserve all v1 question behaviors;
- resolve all three expenses metrics and category aliases;
- reject unsupported/ambiguous/disallowed dimensions;
- compile the shared SQLite/MySQL-prepared qmark representation deterministically;
- prove filter values are parameters;
- execute expenses metrics on SQLite;
- prove explain never calls the executor;
- verify success/failure answer contracts.

### 12.3 Schema tests

- accept an exact or superset snapshot;
- report missing tables and columns together;
- verify the MySQL metadata query is parameterized;
- validate demo and expenses profiles against real MySQL.

### 12.4 MySQL integration tests

On disposable MySQL 8:

- setup completes and runtime identity is non-root;
- demo and expenses profile schemas validate;
- at least three expenses questions match SQLite results;
- category filter is bound;
- SELECT succeeds;
- INSERT, UPDATE, and DELETE fail for the runtime user;
- malformed configuration and schema mismatches fail explicitly;
- no SQLite fallback occurs.

### 12.5 Full acceptance

Run the repository Local Acceptance Gate, fixed benchmark, Eval SHA guard,
Project03 suite, Project00 integration suite, real MySQL suite, and hosted GitHub
Actions. Record exact commands, versions, counts, hashes, and workflow URL in the
final report.

## 13. Incremental Implementation Order

1. Add profile dataclasses, strict loader, and profile unit tests.
2. Encode the demo profile and migrate catalog/resolver behind default loading.
3. Replace compiler branches with the finite operation compiler.
4. Add schema derivation/validation and pure tests.
5. Add expenses profile/schema and SQLite runtime tests.
6. Add CLI ask/explain/validate behavior and answer-contract tests.
7. Extend MySQL setup/integration tests.
8. Run stable benchmark and all acceptance gates.
9. Update user docs and evidence, commit, push, and verify hosted CI.

Each step must keep existing tests green or explain a deliberate test update.
No Eval Set, benchmark classifier, or grading threshold may be modified.

## 14. Decision Status

All MVP-shaping decisions are resolved:

- JSON, not Python/YAML;
- external declarative profiles, no raw SQL;
- two finite operation types;
- strict fail-fast validation;
- required schema derived from operations;
- optional preflight against MySQL metadata;
- default demo compatibility;
- expenses as the non-demo proof;
- explain as a no-execution path;
- CLI first; Web UI, LLM, RAG, and agent frameworks remain out of scope.

Implementation is authorized by the PRD once this document is present. Any
need for arbitrary SQL or a third operation type is an architecture change and
must return to design review instead of being improvised in code.
