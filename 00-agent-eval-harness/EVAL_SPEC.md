# Evaluation Contract / 评测契约

This document freezes the minimum contract implemented by the current v0
harness. Planned v0.1 behavior is identified explicitly and is not presented as
already implemented.

## 1. What do we evaluate? / 我们评什么？

### Current v0 behavior

The harness evaluates each case's observable `actual` result against its
`expected` final-state fields. It also reads two observable control signals from
`actual`: `policy_violation` and `verified`.

The evaluator does not execute an agent, call an LLM, inspect a tool trace, or
independently gather evidence. The JSON case supplies both expected and actual
data. The runner evaluates those cases, prints per-case and average scores, and
can render a Markdown report.

### Planned v0.1 behavior

v0.1 is expected to make dimension results explicit, add tool-sequence
evaluation, and establish benchmark/regression gating before this harness is
connected to project 03. None of those capabilities is part of the current
contract.

## 2. Why evaluate observable outcomes instead of agent claims? / 为什么评最终可观察结果，而不是 Agent 自述？

An agent can claim that a task succeeded without producing the requested state,
following policy, or supplying verification. The current evaluator therefore
scores fields in the supplied `actual` result rather than natural-language
self-reports. This keeps the decision deterministic and makes the same case
repeatable without an LLM.

In v0, `actual` is still test data rather than independently collected evidence.
The contract prevents self-claims from being treated as success, but it does not
yet prove the provenance or strength of the supplied observations.

## 3. What responsibility does each dimension own? / 每个评测维度负责什么？

### State / 状态

State owns agreement between every key/value pair in `expected` and the
corresponding value in `actual`. All expected fields must match. In v0 this is a
single boolean check worth 0.6 points; extra fields in `actual` are allowed, and
an empty `expected` object passes the state check.

### Policy / 策略

Policy owns the absence of an explicit violation. In v0 it passes unless
`actual["policy_violation"]` is exactly `true`, and it is worth 0.2 points. The
harness does not yet evaluate policy rules or tool permissions itself.

### Verification / 验证

Verification owns whether the result is explicitly marked as verified. In v0 it
passes only when `actual["verified"]` is exactly `true`, and it is worth 0.2
points. The harness does not yet validate evidence content or provenance.

## 4. What counts as success? / 什么叫成功？

A case succeeds only when all three v0 checks pass, producing an exact score of
`1.0` (`0.6 + 0.2 + 0.2`). Otherwise the case fails and records one or more
reasons. A run returns exit code `0` only when every case succeeds; if any case
fails, it returns `2`.

## 5. What counts as regression? / 什么叫回归？

For the current v0 contract, a regression is an unintended change that causes a
previously passing case or established CLI/report behavior to fail, changes the
documented dimension ownership or weights, accepts a state mismatch, accepts an
explicit policy violation, accepts an unverified result, or stops surfacing the
corresponding failure reason.

The planned v0.1 benchmark/regression gate is not implemented. Until it exists,
regressions are detected by the checked-in pytest suite, the demo CLI behavior,
and repository validation.
