# Evaluation Contract / 评测契约

This document freezes the minimum contract implemented by the dimensional and
tool-policy evaluation harness.

## 1. What do we evaluate? / 我们评什么？

Each case must contain a non-empty string `id` plus object-valued `expected` and
`actual` fields. `category` is optional and defaults to `uncategorized`. Static
benchmark fixtures also require boolean `expected_success`, which states the
expected evaluator verdict for that hand-written `actual`. It is independent of
`expected`, which still describes the desired final state. The harness evaluates
three independent aspects of the supplied observable result:

- State: whether `actual` contains every expected final-state value.
- Policy: whether behavior obeys explicit deterministic policy and tool rules.
- Verification: whether `actual` records that verification actually occurred.

Each dimension produces a `DimensionResult` with its own normalized `score`
(`0.0` or `1.0`), `passed` flag, `reason`, and `applicable` flag. `EvalResult`
contains all three dimension results plus the derived `overall_score` and
`success` fields.

Cases may declare a non-empty, duplicate-free `required_dimensions` array using
only `state`, `policy`, and `verification`. If omitted, all three dimensions are
required, preserving every existing fixture's behavior. This is a case
expectation contract; it is never inferred from runtime status strings.

Cases can provide an observed tool trace in `actual.tool_calls` and deterministic
constraints in `tool_policy`:

- `required_tools`: every listed tool must appear in the trace.
- `forbidden_tools`: no listed tool may appear in the trace.
- `tool_order`: each `[before, after]` pair requires both tools and requires the
  first `before` occurrence to precede the first `after` occurrence.

Missing `actual.tool_calls` is treated as an empty trace. That preserves old
cases without tool rules while giving required/order rules explicit missing-tool
semantics. Present traces and rules must use JSON arrays of non-empty tool names;
malformed structures are rejected with stable `ValueError` messages.

The harness does not execute an agent, call an LLM, or independently collect the
trace or verification evidence. The JSON case supplies expected and actual data.

## 2. Why evaluate observable outcomes instead of agent claims? / 为什么评最终可观察结果，而不是 Agent 自述？

An agent can claim success without producing the requested state, respecting
policy, or verifying the result. Natural-language confidence therefore does not
affect any dimension. For example, an `actual` object may contain
`"claimed_success": true`, but the case still fails when `verified` is not
exactly `true`.

Observable fields keep evaluation deterministic and repeatable without an LLM.
However, v0.1 still trusts the supplied `actual` object; it does not prove the
provenance or sufficiency of external evidence.

## 3. What responsibility does each dimension own? / 每个评测维度负责什么？

### State / 状态

State owns only final-state agreement. It passes when every key/value pair in
`expected` equals the corresponding value in `actual`. Extra actual fields are
allowed, and an empty `expected` object passes. A state mismatch does not make
Policy or Verification fail.

### Policy / 策略

Policy owns deterministic behavior constraints. It fails when
`actual["policy_violation"]` is exactly `true`, a required tool is missing, a
forbidden tool appears, or an order rule is violated. All applicable failures are
reported in the Policy reason with the relevant tool names. A Policy failure
does not change State or Verification.

Tool Sequence Evaluation remains inside Policy rather than becoming a fourth
dimension because it supplies evidence about allowed behavior. It does not judge
the final state or whether verification occurred.

### Verification / 验证

Verification owns only the explicit verification signal. It passes when
`actual["verified"]` is exactly `true`; otherwise it fails. Agent claims do not
substitute for this signal. v0.1 does not yet validate evidence content or
provenance.

Verification is a conditional responsibility. A workflow that produces a final
query result can require it, while a correctly handled clarification or
pre-execution safety rejection can mark it not applicable by omitting it from
`required_dimensions`. Missing required verification is FAIL; non-required
verification is N/A. The evaluator does not recognize business states to make
this choice.

## 4. What counts as success? / 什么叫成功？

The overall score preserves the existing weights but includes only required
dimensions and normalizes by their combined weight:

`overall_score = sum(required score × weight) / sum(required weight)`

For example, with State and Policy required and Verification N/A, two passing
dimensions score `(1×0.6 + 1×0.2) / 0.8 = 1.0`. Cases that omit
`required_dimensions` retain the original `0.6 / 0.2 / 0.2` calculation.

`success` is not a configurable score threshold. It is `true` only when every
required dimension passes. A non-required dimension cannot fail the case. The
CLI returns `0` only when every case succeeds and returns `2` when any case
fails.

The compatibility properties `score` and `reason` are derived views of the new
model: `score` aliases `overall_score`, while `reason` combines only failed
dimension reasons. They do not store a second result model.

An overall score alone is insufficient for debugging. For example,
`overall_score = 0.8` cannot tell an engineer whether Policy failed or
Verification failed because both currently carry weight `0.2`. Dimension-level
scores, flags, and reasons identify the responsible layer.

Final state alone is also insufficient. An agent can produce the requested
record while calling a forbidden destructive `delete` tool on the way. In that
case State passes, Policy fails with `forbidden tools used: delete`, Verification
may pass, and the overall result still fails.

## 5. Eval, Benchmark, and Regression Gate

An Eval judges one case. A Benchmark aggregates a fixed set of Eval results. A
Regression Gate compares Benchmark metrics with explicit thresholds.

The benchmark intentionally separates:

- `outcome_success_rate`: the fraction of supplied executions whose
  `EvalResult.success` is true. This describes the tested Agent/execution.
- `evaluator_conformance_rate`: the fraction whose evaluator verdict equals the
  fixture's `expected_success`. This describes whether the harness follows its
  fixture contract.

These rates must not be conflated. The current 33-case corpus is primarily a
harness validation corpus with adversarial, intentionally failing outcomes. Its
low outcome rate is expected; its conformance rate should be 100%. A meaningful
production Agent success rate requires a real execution adapter such as the
planned project 03 integration.

Benchmark summaries include total cases, both rates, State/Policy/Verification
and overall averages, per-category counts and rates, failing-dimension counts,
top outcome failure categories/reasons, and conformance mismatch IDs. JSON output
is deterministic and has no timestamps. Markdown presents the same key metrics.
Per-dimension averages include applicable cases only; overall averages use each
case's already normalized applicable-dimension score.

Optional `metrics.latency_ms` and `metrics.cost` are aggregated only when actual
values are supplied. Otherwise JSON uses unavailable/null fields and Markdown
states `not available`; the harness never invents measurements.

The default gate config checks only `min_evaluator_conformance_rate: 1.0`.
Dimension, overall, and outcome thresholds are supported but optional. In
particular, outcome success is not a default gate for this adversarial corpus.
Gate failures identify the metric, actual value, and threshold and return exit
code `3`. Benchmark generation without a violated gate returns `0`, regardless
of intentional outcome failures. The legacy single-run CLI keeps exit code `2`
when any case outcome fails.

## 6. What counts as regression? / 什么叫回归？

A v0.1 regression includes any unintended change that:

- makes one dimension's failure contaminate another dimension;
- changes the legacy all-required `0.6 / 0.2 / 0.2` aggregation semantics;
- reports success while any required dimension fails;
- treats an N/A dimension as a failure or includes it in the score denominator;
- accepts a malformed case instead of producing a clear validation error;
- accepts a missing required tool, a forbidden tool, or an invalid tool order;
- changes State or Verification merely because a tool rule failed;
- removes dimension evidence from the Markdown report; or
- breaks the established demo, CLI exit codes, summary table, or report output.

For the static fixture corpus, a regression is established by the Regression
Gate, primarily when evaluator conformance drops below its configured threshold.
An intentional outcome failure that still matches `expected_success` is not a
regression.

Baseline-file comparison is not implemented because the explicit threshold gate
already gives the current small harness a clear deterministic boundary.

## 7. Real project 03 integration / 真实 03 集成

The project 03 system benchmark has a different provenance from the 33-case
harness corpus:

`integration request -> project 03 public interface -> 03 raw result -> thin adapter -> actual -> evaluate -> benchmark`

The adapter runs outside project 03. Project 03 remains independently runnable
and has no dependency on project 00. The adapter renames `trace` to `tool_calls`
and otherwise preserves raw fields; it does not infer success, policy safety, or
verification. Integration fixtures containing a precomputed `actual` are
rejected.

Current field ownership is:

- State: project 03 `status`, `metric`, `evidence`, or structured policy
  `allowed/reason` fields.
- Policy: project 03's real `validate_sql` decision plus the stages actually
  present in its `trace`.
- Verification: project 03's `verified` signal. Successful metric queries derive
  it from a deterministic check that the expected metric key is present and
  non-null.
- Tool trace: stages appended by project 03 as they execute. Unknown metrics
  stop after `resolve_metric`; policy-only calls record only `validate_sql`.

The verification evidence remains intentionally limited. It proves that project
03 produced and checked a metric-shaped result, not that an independent system
validated business correctness or evidence provenance. The adapter does not
fill missing verification signals. Instead, the integration case contract
requires Verification for normal metric queries and marks it N/A for correct
clarification and standalone policy decisions.

For the integration corpus, `outcome_success_rate` is a real baseline for the
current project 03 system on those fixed inputs. `evaluator_conformance_rate`
still checks whether project 00's verdict matches the case contract. These
metrics must remain separate from the identically named metrics of the static
Harness Benchmark.

This integration completes project 00's independent scope. Future evaluator
changes require a reproducible real project 03 bad case; they are not added as
framework features in isolation.
