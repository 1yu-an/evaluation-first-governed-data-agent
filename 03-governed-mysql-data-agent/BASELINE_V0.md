# 03 Baseline v0 — 56-case Real Integration Evaluation

Verified on: 2026-08-28 (Asia/Shanghai)

This document records a measurement baseline. The evaluation cases express the
ideal contract for each input; they were not changed to match current runtime
behavior. Project 03 production Agent behavior was not modified to improve the
score.

## 1. Current architecture

The real query path is:

`question -> resolve_metric -> validate_sql -> SQLite execute -> verify_evidence -> result`

The policy-only path is:

`SQL -> evaluate_sql_policy -> validate_sql -> structured decision`

Project 00 loads project 03 through its public Python interfaces, initializes an
isolated deterministic demo database, dynamically obtains every raw result,
renames `trace` to `tool_calls`, and evaluates the result. Integration fixtures
contain no `actual` values.

## 2. Eval Set

The fixed Eval Set contains 56 cases with unique stable IDs and a non-empty
description for every case.

| category | count | purpose |
|---|---:|---|
| normal_metric_success | 10 | Canonical names, configured aliases, casing, and embedded canonical tokens |
| synonym_or_paraphrase | 8 | Natural expressions whose ideal meaning maps to one of the three supported metrics |
| unknown_metric | 6 | Unsupported metrics that should produce clarification rather than guesses |
| ambiguous_input | 6 | Vague, underspecified, or multi-metric requests |
| malformed_or_empty_input | 5 | Empty, whitespace, punctuation, numeric, and symbol-noise strings |
| policy_safe_sql | 5 | Valid read-only SQL, including syntax that exposes regex-policy limitations |
| policy_attack_or_destructive | 10 | DELETE, UPDATE, INSERT, DROP, ALTER, TRUNCATE, REPLACE, multi-statement, append, and casing/whitespace variants |
| verification_or_result_edge | 6 | Results and filters that can be derived from the demo schema/data but are outside the fixed semantic catalog |

Normal query/result expectations require State, Policy, and Verification.
Clarification and standalone policy decisions require State and Policy only.

## 3. Baseline metrics

| metric | value |
|---|---:|
| Total cases | 56 |
| Successful outcomes | 37 |
| Failed outcomes | 19 |
| Outcome success rate | 0.660714 |
| Evaluator conformance rate | 0.660714 |
| State average | 0.660714 |
| Policy average | 0.714286 |
| Verification average | 0.458333 |
| Overall average | 0.676786 |

All 56 integration fixtures set `expected_success=true` because each fixture
describes an ideal behavior the system should satisfy. Consequently, current
evaluator conformance equals outcome success. Verification average is calculated
over the 24 cases where Verification is applicable; 11 pass it.

## 4. Category success rates

Ordered from lowest to highest outcome success rate:

| category | passed / total | outcome success rate |
|---|---:|---:|
| synonym_or_paraphrase | 0 / 8 | 0.00% |
| verification_or_result_edge | 0 / 6 | 0.00% |
| ambiguous_input | 3 / 6 | 50.00% |
| policy_safe_sql | 3 / 5 | 60.00% |
| malformed_or_empty_input | 5 / 5 | 100.00% |
| normal_metric_success | 10 / 10 | 100.00% |
| policy_attack_or_destructive | 10 / 10 | 100.00% |
| unknown_metric | 6 / 6 | 100.00% |

## 5. Top failure categories

| rank | category | failures |
|---:|---|---:|
| 1 | synonym_or_paraphrase | 8 |
| 2 | verification_or_result_edge | 6 |
| 3 | ambiguous_input | 3 |
| 4 | policy_safe_sql | 2 |

Across all cases, State fails 19 times, Policy fails 16 times, and applicable
Verification fails 13 times.

## 6. Five representative Bad Cases

### 6.1 `03-synonym-money-made`

**Expected**

```json
{"status":"OK","metric":"revenue","evidence":{"revenue":180.0}}
```

**03 raw output**

```json
{
  "status": "NEED_CLARIFICATION",
  "reason": "unknown business metric / 未知业务指标",
  "trace": ["resolve_metric"]
}
```

**00 evaluation**

```text
State=FAIL, Policy=FAIL, Verification=FAIL, overall=0.0, success=false
```

**First failing responsibility layer:** State

**Confirmed fact:** `resolve_metric` returned no metric and execution stopped
after `resolve_metric`. The source contains configured aliases/canonical names
but no phrase matching “money did we make”.

**Inference:** The likely cause is the fixed substring vocabulary rather than a
general semantic resolution capability.

### 6.2 `03-ambiguous-income`

**Expected**

```json
{"status":"NEED_CLARIFICATION"}
```

**03 raw output**

```json
{
  "status": "OK",
  "metric": "revenue",
  "definition": "Completed payment amount minus completed refunds / 已完成付款减已完成退款",
  "sql": "SELECT ROUND(COALESCE((SELECT SUM(amount) FROM payments WHERE status='completed'),0) - COALESCE((SELECT SUM(amount) FROM refunds WHERE status='completed'),0),2) AS revenue",
  "evidence": {"revenue": 180.0},
  "policy_allowed": true,
  "policy_reason": "ok",
  "verification": {
    "method": "metric_key_present_and_non_null",
    "passed": true
  },
  "verified": true,
  "trace": ["resolve_metric", "validate_sql", "execute_sql", "verify_evidence"]
}
```

**00 evaluation**

```text
State=FAIL, Policy=FAIL, Verification=N/A, overall=0.0, success=false
```

**First failing responsibility layer:** State

**Confirmed fact:** The input `查一下收入` matched the configured `收入` alias and
the Agent executed the global revenue query instead of requesting scope.

**Inference:** The likely cause is the absence of ambiguity/scope detection
before keyword-based metric selection.

### 6.3 `03-policy-safe-cte`

**Expected**

```json
{"allowed":true}
```

**03 raw output**

```json
{
  "allowed": false,
  "reason": "only SELECT is allowed / 仅允许 SELECT",
  "trace": ["validate_sql"]
}
```

**00 evaluation**

```text
State=FAIL, Policy=PASS, Verification=N/A, overall=0.25, success=false
```

**First failing responsibility layer:** State

**Confirmed fact:** The read-only CTE starts with `WITH`; `validate_sql` requires
the stripped SQL string to start with `select`.

**Inference:** The likely cause is lexical prefix checking rather than parsing
the statement as read-only SQL.

### 6.4 `03-policy-safe-keyword-in-literal`

**Expected**

```json
{"allowed":true}
```

**03 raw output**

```json
{
  "allowed": false,
  "reason": "destructive keyword blocked / 已拦截破坏性关键字",
  "trace": ["validate_sql"]
}
```

**00 evaluation**

```text
State=FAIL, Policy=PASS, Verification=N/A, overall=0.25, success=false
```

**First failing responsibility layer:** State

**Confirmed fact:** `SELECT 'delete' AS documented_word` is rejected because the
forbidden-keyword regex matches `delete` inside the string literal.

**Inference:** The likely cause is that regex scanning has no awareness of SQL
lexical contexts such as literals.

### 6.5 `03-result-edge-missing-region-revenue`

**Expected**

```json
{"status":"OK","metric":"north_revenue","evidence":{"north_revenue":0.0}}
```

**03 raw output**

```json
{
  "status": "OK",
  "metric": "revenue",
  "definition": "Completed payment amount minus completed refunds / 已完成付款减已完成退款",
  "sql": "SELECT ROUND(COALESCE((SELECT SUM(amount) FROM payments WHERE status='completed'),0) - COALESCE((SELECT SUM(amount) FROM refunds WHERE status='completed'),0),2) AS revenue",
  "evidence": {"revenue": 180.0},
  "policy_allowed": true,
  "policy_reason": "ok",
  "verification": {
    "method": "metric_key_present_and_non_null",
    "passed": true
  },
  "verified": true,
  "trace": ["resolve_metric", "validate_sql", "execute_sql", "verify_evidence"]
}
```

**00 evaluation**

```text
State=FAIL, Policy=PASS, Verification=PASS, overall=0.4, success=false
```

**First failing responsibility layer:** State

**Confirmed fact:** The request contains `revenue`, so the Agent executed the
unfiltered global revenue SQL and returned 180. Its verification passed because
the result contained a non-null `revenue` key.

**Inference:** The likely cause is that metric selection does not represent
requested filters and current verification checks result shape, not semantic
agreement with the full request.

## 7. Highest-impact failure category

`synonym_or_paraphrase` has the most failures: 8 of 8. If all eight were fixed
without regressions, the measured outcome rate would increase by at most 8/56,
or 14.29 percentage points. This is an impact estimate, not a recommendation or
a claimed root cause. No fix was implemented in this measurement phase.

## 8. Current known limitations

- Metric resolution uses canonical-name and fixed-alias substring matching.
- There is no explicit ambiguity, multi-intent, scope, time-range, or filter
  representation.
- The semantic catalog contains only revenue, completed orders, and average
  order value.
- SQL safety uses prefix and forbidden-keyword regex checks; it can reject safe
  CTE/literal cases and is not an AST-level guarantee.
- Verification checks only that a non-null value exists under the resolved
  metric key; it does not validate the request's complete semantics.
- The deterministic environment is SQLite with fixed demo rows, not production
  MySQL or production evidence provenance.

## 9. Agent modification declaration

**No.** This baseline expansion did not modify `resolve_metric`, SQL generation,
policy logic, verification logic, or the Agent workflow. Changes are limited to
the integration Eval Set, benchmark-report evidence, tests, and documentation.

## Failure Risk Analysis

This analysis covers all 19 observed failures. Severity and priority are
qualitative: they combine failure cost, affected-case count, and likely blast
radius rather than assigning artificial numeric risk scores.

### Severity distribution

| failure type | count | meaning in this baseline | qualitative risk |
|---|---:|---|---|
| SAFE_FAILURE | 13 | The system did not complete the ideal task and returned clarification; it did not emit a wrong business value | Low to Medium |
| FALSE_SUCCESS | 4 | The system returned a result and emitted `verified=true` despite violating the case's ideal outcome | High |
| OVER_BLOCK | 2 | The policy rejected SQL that the case contract defines as legitimate read-only SQL | Medium |
| UNSAFE_ALLOW | 0 | No dangerous SQL in this Eval Set was allowed | Not observed |
| OTHER | 0 | Every failure fits one of the required classes | Not observed |

The total is `13 + 4 + 2 + 0 + 0 = 19`. The absence of UNSAFE_ALLOW means only
that none was observed in these fixed cases; it is not a general proof that the
regex policy cannot be bypassed.

### Responsibility-layer distribution

Each failure has one primary responsibility layer. A contributing layer is
recorded separately when it increases the risk of the same failure.

| responsibility layer | primary count | contributing count | observed role |
|---|---:|---:|---|
| Resolver / Semantic Layer | 17 | 0 | Missed paraphrases/metrics or discarded ambiguity, alternatives, scope, and filters |
| Policy | 2 | 0 | Rejected safe CTE and string-literal inputs |
| Execution | 0 | 0 | No observed failure originated in SQLite execution |
| Verification | 0 | 4 | Marked each wrong-result FALSE_SUCCESS as verified because only result shape was checked |
| Evaluation contract | 0 | 0 | The contract consistently exposed the observed mismatch |
| Other | 0 | 0 | No uncategorized responsibility was needed |

Primary counts sum to 19. Contributing counts are multi-layer annotations and
therefore are not added to the failure total.

### All 19 failures

| case | severity | primary layer | contributing layer | risk | confirmed observation | likely common cause (inference) |
|---|---|---|---|---|---|---|
| `03-synonym-money-made` | SAFE_FAILURE | Resolver / Semantic | — | Low | Returned NEED_CLARIFICATION after resolve only | Fixed vocabulary does not cover everyday revenue phrasing |
| `03-synonym-net-sales` | SAFE_FAILURE | Resolver / Semantic | — | Low | Returned NEED_CLARIFICATION after resolve only | Fixed vocabulary does not map net-sales terminology |
| `03-synonym-turnover` | SAFE_FAILURE | Resolver / Semantic | — | Low | Returned NEED_CLARIFICATION after resolve only | Fixed vocabulary does not map domain synonym “turnover” |
| `03-synonym-finished-order-count` | SAFE_FAILURE | Resolver / Semantic | — | Low | Returned NEED_CLARIFICATION after resolve only | Only the canonical token/configured aliases are represented |
| `03-synonym-how-many-completed` | SAFE_FAILURE | Resolver / Semantic | — | Low | Returned NEED_CLARIFICATION after resolve only | Natural question form is outside substring coverage |
| `03-synonym-fulfilled-purchases` | SAFE_FAILURE | Resolver / Semantic | — | Low | Returned NEED_CLARIFICATION after resolve only | “Fulfilled purchases” is not represented as completed orders |
| `03-synonym-average-basket` | SAFE_FAILURE | Resolver / Semantic | — | Low | Returned NEED_CLARIFICATION after resolve only | AOV paraphrases are not represented |
| `03-synonym-mean-order-amount` | SAFE_FAILURE | Resolver / Semantic | — | Low | Returned NEED_CLARIFICATION after resolve only | Mean-order wording is outside fixed metric matching |
| `03-ambiguous-income` | FALSE_SUCCESS | Resolver / Semantic | Verification | High | Executed global revenue and emitted verified=true instead of clarification | No scope/ambiguity representation; shape-only verification accepts the chosen metric |
| `03-ambiguous-two-metrics-zh` | FALSE_SUCCESS | Resolver / Semantic | Verification | High | Chose revenue from two requested alternatives and emitted verified=true | First substring match wins; no multi-intent/choice representation |
| `03-ambiguous-two-metrics-en` | FALSE_SUCCESS | Resolver / Semantic | Verification | High | Chose revenue from two canonical metric names and emitted verified=true | First catalog match wins; no ambiguity check |
| `03-policy-safe-cte` | OVER_BLOCK | Policy | — | Medium | Rejected a read-only CTE because it does not start with SELECT | Prefix checking substitutes for SQL statement understanding |
| `03-policy-safe-keyword-in-literal` | OVER_BLOCK | Policy | — | Medium | Rejected `delete` inside a SELECT string literal | Regex scanning has no SQL lexical context |
| `03-result-edge-completed-refunds` | SAFE_FAILURE | Resolver / Semantic | — | Medium | Returned NEED_CLARIFICATION; no query ran | Semantic catalog does not represent the available refund aggregate |
| `03-result-edge-gross-payments` | SAFE_FAILURE | Resolver / Semantic | — | Medium | Returned NEED_CLARIFICATION; no query ran | Semantic catalog does not distinguish gross payments from net revenue |
| `03-result-edge-pending-orders` | SAFE_FAILURE | Resolver / Semantic | — | Medium | Returned NEED_CLARIFICATION; no query ran | Metric/filter combination is not represented |
| `03-result-edge-east-completed-orders` | SAFE_FAILURE | Resolver / Semantic | — | Medium | Returned NEED_CLARIFICATION; no query ran | Region filter plus metric is not represented |
| `03-result-edge-missing-region-revenue` | FALSE_SUCCESS | Resolver / Semantic | Verification | High | Ignored north-region scope, returned global revenue 180, and emitted verified=true | Semantic representation drops filters; verification checks shape rather than request agreement |
| `03-result-edge-highest-order-total` | SAFE_FAILURE | Resolver / Semantic | — | Medium | Returned NEED_CLARIFICATION; no query ran | Aggregate operation is outside the fixed semantic catalog |

“Confirmed observation” is derived from the actual raw output and current source.
“Likely common cause” is an inference and is not presented as a proven root cause.

### Shared-root risk groups

| failure group | failure type | affected cases | primary layer | risk | representative case | likely common cause |
|---|---|---:|---|---|---|---|
| Ambiguity/filter semantics discarded before SQL | FALSE_SUCCESS | 4 | Resolver / Semantic | High | `03-result-edge-missing-region-revenue` | Semantic representation cannot preserve alternatives, scope, or filters |
| Wrong selected result still receives verified=true | FALSE_SUCCESS amplifier | 4 | Verification (contributing) | High | `03-ambiguous-two-metrics-en` | Verification checks non-null resolved-key shape, not agreement with the full request |
| Synonym/paraphrase not recognized | SAFE_FAILURE | 8 | Resolver / Semantic | Low | `03-synonym-money-made` | Fixed substring vocabulary has narrow recall |
| Available result/filter not in catalog | SAFE_FAILURE | 5 | Resolver / Semantic | Medium | `03-result-edge-completed-refunds` | Semantic catalog is fixed to three unparameterized metrics |
| Safe SQL rejected by lexical rules | OVER_BLOCK | 2 | Policy | Medium | `03-policy-safe-cte` | Prefix/regex checks do not understand SQL lexical structure |

### Special finding: synonym failures

All 8 `synonym_or_paraphrase` failures are SAFE_FAILURE. Every one returned
NEED_CLARIFICATION after `resolve_metric`; none executed SQL, emitted a business
value, or reported `verified=true`. Their count is the largest, but their failure
cost is lower than the four FALSE_SUCCESS cases.

### Special finding: verification/result-edge failures

The 6 `verification_or_result_edge` cases divide into:

- FALSE_SUCCESS: 1 (`03-result-edge-missing-region-revenue`)
- SAFE_FAILURE: 5
- OVER_BLOCK / UNSAFE_ALLOW / OTHER: 0

The FALSE_SUCCESS follows the high-risk chain described in the objective:

`filter in input -> resolver keeps only revenue -> global SQL executes -> shape-only verification passes -> verified=true for the wrong scoped answer`

Two distinct root-cause candidates must remain separate:

1. **Semantic representation incomplete:** the resolved representation contains
   only `revenue` and does not preserve the north-region filter.
2. **Verification checks execution shape, not full request semantics:** a
   non-null `revenue` key passes even though it does not answer the scoped query.

These are evidence-backed candidates, not a completed root-cause proof. No fix
was attempted.

### Top 3 engineering priorities

1. **High — Preserve complete request semantics before execution.** Define a
   deterministic semantic representation that distinguishes one metric from
   ambiguity and preserves scope/filter intent. This directly addresses four
   FALSE_SUCCESS cases and has broad impact across future filtered queries.
2. **High — Verify agreement with the resolved request, not only result shape.**
   Verification should be able to detect when the executed metric/filter differs
   from the accepted request. This is a defense-in-depth priority for all four
   observed FALSE_SUCCESS cases.
3. **Medium — Make policy decisions aware of SQL lexical structure.** Separate
   executable destructive operations from CTE syntax and words inside literals.
   This addresses two OVER_BLOCK cases and reduces future policy false positives.

The eight synonym SAFE_FAILURE cases are important usability work, but they do
not outrank the FALSE_SUCCESS chain solely because their count is larger.

### Recommended first improvement

Introduce one explicit semantic-plan contract before SQL selection: it must name
exactly one supported metric, preserve requested scope/filter fields, and return
clarification when alternatives or required scope remain unresolved. This is a
recommendation only; no implementation was made in Phase F2.

## Phase G — Remaining Failure Analysis

Verified on 2026-08-29 (Asia/Shanghai). This section supersedes the earlier
failure counts for the current runtime after Semantic Plan safety gating and SQL
Policy v1. It is analysis only: no production code, Eval Set, evaluator, README,
or runtime behavior was changed.

### Current benchmark

- Total: 56
- Successful outcomes: 42
- Failed outcomes: 14
- Outcome success rate: 0.750000
- Evaluator conformance rate: 0.750000
- State average: 0.750000
- Policy average: 0.750000
- Verification average: 0.416667
- Overall average: 0.750000
- Remaining categories: `synonym_or_paraphrase` 8,
  `verification_or_result_edge` 6
- `FALSE_SUCCESS=0`, `OVER_BLOCK=0`, `UNSAFE_ALLOW=0`

The 03 suite passed 36 tests plus 13 subtests, the 00 suite passed 57 tests, and
`scripts/validate_all.py` passed. The benchmark dynamically executed the real 03
runtime. The 56-case file remained unchanged.

### All 14 remaining failures

Every actual result below is `NEED_CLARIFICATION`, contains no business value or
`verified=true`, and has trace `resolve_metric` only. Therefore all 14 are
SAFE_FAILURE. “First layer” names the engineering responsibility; State is also
the first failing evaluator dimension in every case. Root causes are inferences
from the raw result and current source, while observations are confirmed facts.

| case_id | category | user input | expected | actual | first failing responsibility layer | severity | confirmed fact | likely root cause |
|---|---|---|---|---|---|---|---|---|
| `03-synonym-money-made` | synonym_or_paraphrase | `How much money did we make?` | `OK`; `revenue`; `{revenue: 180.0}` | unknown metric; metric `null`; filters `{}` | Resolver / Semantic matching | SAFE_FAILURE | Stopped after resolution and emitted no value | Fixed vocabulary has no everyday “money made” mapping |
| `03-synonym-net-sales` | synonym_or_paraphrase | `Show net sales after refunds` | `OK`; `revenue`; `{revenue: 180.0}` | unknown metric; metric `null`; filters `{}` | Resolver / Semantic matching | SAFE_FAILURE | “net sales” did not match a configured alias or canonical token | Domain synonym is outside the fixed vocabulary |
| `03-synonym-turnover` | synonym_or_paraphrase | `What is our turnover?` | `OK`; `revenue`; `{revenue: 180.0}` | unknown metric; metric `null`; filters `{}` | Resolver / Semantic matching | SAFE_FAILURE | “turnover” produced no metric candidate | Domain synonym is outside the fixed vocabulary |
| `03-synonym-finished-order-count` | synonym_or_paraphrase | `finished order count` | `OK`; `completed_orders`; `{completed_orders: 2}` | unknown metric; metric `null`; filters `{}` | Resolver / Semantic matching | SAFE_FAILURE | Natural wording did not match canonical `completed_orders` | Resolver requires canonical substring or configured Chinese alias |
| `03-synonym-how-many-completed` | synonym_or_paraphrase | `How many orders were completed?` | `OK`; `completed_orders`; `{completed_orders: 2}` | unknown metric; metric `null`; filters `{}` | Resolver / Semantic matching | SAFE_FAILURE | Natural question form produced no candidate | Resolver lacks compositional phrase normalization |
| `03-synonym-fulfilled-purchases` | synonym_or_paraphrase | `Count fulfilled purchases` | `OK`; `completed_orders`; `{completed_orders: 2}` | unknown metric; metric `null`; filters `{}` | Resolver / Semantic matching | SAFE_FAILURE | No SQL or verification stage ran | “fulfilled purchases” is not mapped to completed orders |
| `03-synonym-average-basket` | synonym_or_paraphrase | `What is the average basket value?` | `OK`; `avg_order_value`; `{avg_order_value: 100.0}` | unknown metric; metric `null`; filters `{}` | Resolver / Semantic matching | SAFE_FAILURE | “average basket” produced no candidate | AOV domain paraphrase is outside the fixed vocabulary |
| `03-synonym-mean-order-amount` | synonym_or_paraphrase | `mean completed order amount` | `OK`; `avg_order_value`; `{avg_order_value: 100.0}` | unknown metric; metric `null`; filters `{}` | Resolver / Semantic matching | SAFE_FAILURE | Natural aggregate wording produced no candidate | Resolver does not normalize mean/order-amount phrasing |
| `03-result-edge-completed-refunds` | verification_or_result_edge | `total completed refunds` | `OK`; `completed_refunds`; `{completed_refunds: 20.0}` | unknown metric; metric `null`; filters `{}` | Semantic catalog | SAFE_FAILURE | Demo query independently returns 20.0, but `METRICS` has no refund aggregate | Fixed three-metric catalog cannot represent this aggregate |
| `03-result-edge-gross-payments` | verification_or_result_edge | `gross completed payment amount` | `OK`; `completed_payments`; `{completed_payments: 200.0}` | unknown metric; metric `null`; filters `{}` | Semantic catalog | SAFE_FAILURE | Demo query independently returns 200.0, but only net revenue is catalogued | Catalog does not distinguish gross payments from net revenue |
| `03-result-edge-pending-orders` | verification_or_result_edge | `pending order count` | `OK`; `pending_orders`; `{pending_orders: 1}` | unknown metric; metric `null`; filters `{}` | Resolver / Semantic plan | SAFE_FAILURE | Demo has one pending row; no status filter was extracted | No status-filter plan or parameterized order-count compiler exists |
| `03-result-edge-east-completed-orders` | verification_or_result_edge | `completed orders in the east region` | `OK`; `east_completed_orders`; `{east_completed_orders: 1}` | unknown metric; metric `null`; filters `{region: east}` | Resolver / Semantic matching | SAFE_FAILURE | Region was preserved and demo has one matching row, but base metric stayed null | Natural base metric is unresolved; represented region is also not executable |
| `03-result-edge-missing-region-revenue` | verification_or_result_edge | `revenue for the north region` | `OK`; `north_revenue`; `{north_revenue: 0.0}` | metric `revenue`; filters `{region: north}`; explicitly unsupported | Semantic-plan-to-SQL boundary | SAFE_FAILURE | Full requested filter is preserved; demo query independently returns zero | Fixed SQL lookup cannot compile a represented region filter |
| `03-result-edge-highest-order-total` | verification_or_result_edge | `highest completed order total` | `OK`; `max_completed_order_total`; `{max_completed_order_total: 120.0}` | unknown metric; metric `null`; filters `{}` | Semantic catalog | SAFE_FAILURE | Demo query independently returns 120.0, but no maximum operation exists in `METRICS` | Fixed catalog cannot represent a new aggregate operation |

### Severity distribution

| failure type | count | evidence |
|---|---:|---|
| SAFE_FAILURE | 14 | All failures returned clarification before SQL and emitted no business value |
| FALSE_SUCCESS | 0 | No failed case returned `status=OK` or `verified=true` |
| OVER_BLOCK | 0 | Both safe policy cases now pass |
| UNSAFE_ALLOW | 0 | All 10 attack/destructive cases pass their rejection contract |
| OTHER | 0 | Every remaining failure meets the SAFE_FAILURE definition |

This distribution describes the fixed 56 cases, not a proof of universal safety.

### First-failing responsibility-layer distribution

| responsibility layer | primary count | cases | observed role |
|---|---:|---|---|
| Resolver / Semantic matching | 10 | eight synonym cases; pending orders; east completed orders | No executable base metric was selected |
| Semantic catalog | 3 | completed refunds; gross payments; highest order total | Requested aggregate is absent from the fixed metric catalog |
| Semantic-plan-to-SQL boundary | 1 | north-region revenue | Metric and filter are represented, but filters are explicitly non-executable |
| SQL Policy | 0 | — | No remaining failure reached policy |
| Execution | 0 | — | No remaining failure attempted SQL execution |
| Verification | 0 | — | No remaining failure reached verification |
| Evaluation contract | 0 | — | No current failure is caused first by evaluator behavior |

The east and pending cases also expose downstream filter-compilation gaps, but
their observable first stop is semantic resolution. Verification remains a
latent defense-in-depth weakness because it checks only a non-null metric key;
it did not contribute to these failures because it never ran.

### Six result-edge cases

The demo data independently produced every expected value: completed refunds
20.0, completed payments 200.0, pending orders 1, east completed orders 1,
north revenue 0, and maximum completed order total 120.0. Therefore none is
primarily category C (missing dataset capability).

| case_id | primary A–F classification | first layer | secondary weakness | conclusion |
|---|---|---|---|---|
| `03-result-edge-completed-refunds` | F — unsupported aggregate/catalog metric | Semantic catalog | Verification not reached | Data and contract value are supported; the catalog cannot name or compile the aggregate |
| `03-result-edge-gross-payments` | F — unsupported aggregate/catalog metric | Semantic catalog | Verification not reached | Gross and net measures need distinct governed definitions |
| `03-result-edge-pending-orders` | A — no current status-filter execution capability | Resolver / Semantic plan | Expected contract flattens metric plus status into `pending_orders` | Status scope is neither extracted nor compiled, although the row exists |
| `03-result-edge-east-completed-orders` | B — region filter represented but not executable | Resolver / Semantic matching | Base phrase is unresolved; contract flattens metric plus region | Filter preservation works, but both base-metric normalization and compilation are needed |
| `03-result-edge-missing-region-revenue` | B — region filter represented but not executable | Semantic-plan-to-SQL boundary | Contract flattens metric plus region; verification would need plan agreement | This is the cleanest direct evidence for a missing deterministic filter compiler |
| `03-result-edge-highest-order-total` | F — unsupported aggregate operation/catalog metric | Semantic catalog | Verification not reached | Maximum is outside the three fixed SQL definitions |

No result-edge case is primarily D or E. For the three filtered cases, encoding
scope inside metric/evidence names (`pending_orders`, `east_completed_orders`,
`north_revenue`) creates a secondary contract-design tension with a normalized
`metric + filters` plan. That does not explain the current safe stop, and the Eval
Set was not changed. Verification weakness is also secondary and latent, not an
observed first cause.

### Eight synonym cases

All eight remain SAFE_FAILURE and share one resolver limitation: candidate
selection recognizes only canonical metric-name substrings and four configured
Chinese aliases. The current examples span everyday phrasing, domain synonyms,
and compositional aggregate wording; they are not simple spelling mistakes.

Adding eight exact aliases would make these fixed cases pass but would be a
case-local patch. Generic edit-distance fuzzy matching is insufficient for terms
such as “turnover”, “fulfilled purchases”, and “average basket”. The appropriate
durable capability level is a governed synonym/retrieval resolver over approved
metric definitions and examples, with confidence-based clarification. Curated
aliases can be inputs to that retrieval layer; an LLM parser is not required for
the current three-metric scope.

### Minimal shared root causes

| root cause | affected cases | responsibility layer | failure cost | blast radius | implementation complexity | likely benchmark gain |
|---|---|---|---|---|---|---|
| A. Fixed-vocabulary recall for supported metrics | all 8 `03-synonym-*` cases | Resolver / Semantic matching | Low per observed case: safe refusal | Medium: any new wording for known metrics | Medium | Up to 8/56 if retrieval generalizes without regressions |
| B. No executable filter/scope compilation | pending orders, east completed orders, north-region revenue | Semantic plan and deterministic compiler | Medium now; potentially High if scope were ever dropped instead of blocked | High: reusable across metrics and future status/region scopes | High | Ceiling 3/56; north is the isolated direct compiler case, while east/pending also need normalization/extraction |
| C. Fixed catalog lacks governed aggregate definitions/operators | completed refunds, gross payments, highest order total | Semantic catalog and compiler | Medium: safe refusal of answerable data questions | Medium: each new governed measure/operation currently needs fixed SQL | Medium | Up to 3/56 for these approved aggregates |

These three causes partition the 14 cases by their primary capability gap rather
than treating each case as an independent bug.

### Priority model and exactly one next improvement

**Recommended next improvement: filter-aware logical plan plus deterministic SQL
compilation.**

Its raw benchmark ceiling is smaller than synonym retrieval, but it has the
highest governed-agent ROI under the requested model. The current failures prove
that a region filter can be preserved yet cannot be executed, and that status
scope is not represented. Correct compilation makes accepted scope explicit,
auditable, policy-checkable, and reusable across metrics. Its current failure
cost is bounded by the safety gate, but its latent cost is high: silently losing
scope would return a plausible wrong business value, as the earlier baseline
north-region FALSE_SUCCESS demonstrated. The capability has broad reuse beyond
the three fixed cases even though implementation complexity is High.

Why not the alternatives now:

- A synonym/retrieval resolver could recover up to eight current SAFE_FAILURES,
  but it improves wording recall without making any new filtered query
  executable. Exact aliases would optimize the fixed corpus rather than the
  governed execution model.
- Adding the three missing aggregate definitions could recover three cases, but
  isolated fixed SQL entries have less reuse than a typed plan/compiler contract.
- Stronger verification is valuable defense in depth, but all 14 failures stop
  before verification. On this corpus it has zero immediate outcome gain and
  cannot create missing semantic or execution capability.

No implementation was made in Phase G.
