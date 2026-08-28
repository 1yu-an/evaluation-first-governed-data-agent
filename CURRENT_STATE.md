# Current Repository State

Verified on: 2026-08-28 (Asia/Shanghai)

This file records only facts checked in the current workspace. The Git index
contains the verified baseline snapshot; dimensional evaluation, Tool Sequence
Evaluation, Benchmark Report, Regression Gate, and project 03 integration
changes are kept unstaged in the working tree until Git author identity is
configured.

## Git baseline

- Immediately before the first baseline commit was prepared, the repository had
  no commits: `git log --oneline --all` returned no entries and `git status`
  reported `No commits yet on master`.
- That pre-commit working tree contained staged files, modified files, and
  untracked files. The verified project source, tests, documentation, and project
  assets were collected into the first baseline commit rather than discarded.
- The reproducible `00-agent-eval-harness/reports/` output and Python/pytest
  caches are ignored and are not baseline source artifacts.
- Existing user work was preserved. No reset, checkout, or clean operation was
  performed while establishing the baseline.

## Repository validation

- `scripts/validate_all.py` completed successfully on 2026-08-28.
- The validator confirmed that all seven required project directories exist and
  that the Python and JSON files it scanned were parseable.
- This validator is a structure/syntax check; it is not a substitute for each
  project's behavioral test suite.

## 00-agent-eval-harness

### Tests

- Before the baseline test addition: 10 pytest tests passed.
- After the fixture + monkeypatch test addition: 11 pytest tests passed.
- After dimensional evaluation v0.1: 14 pytest tests passed.
- After Tool Sequence Evaluation and eval-set expansion: 30 pytest tests passed.
- After Benchmark Report and Regression Gate: 41 pytest tests passed.
- Before project 03 integration: 41 pytest tests passed.
- After project 03 integration: 48 project 00 pytest tests passed; project 03
  increased from 3 to 6 passing pytest tests.
- After case-specific required-dimension semantics: 57 project 00 pytest tests
  passed; project 03 remains at 6 passing tests.

### Current capabilities

- Deterministically compares every field in a case's `expected` mapping with the
  supplied observable `actual` mapping.
- Emits independent State, Policy, and Verification results, each with a
  normalized score, pass/fail flag, and reason.
- Derives `overall_score` from the preserved weights: State 0.6, Policy 0.2,
  Verification 0.2.
- Supports case-specific `required_dimensions`, defaulting to all three
  dimensions for full backward compatibility.
- Defines success as every required dimension passing. Non-required dimensions
  are explicitly represented as N/A rather than FAIL.
- Re-normalizes `overall_score` over required dimensions only, so N/A evidence
  never lowers the case score.
- Rejects missing or non-object `expected` and `actual` fields with explicit
  validation errors.
- Evaluates required tools, forbidden tools, and simple pairwise tool order as
  deterministic Policy evidence while preserving State and Verification
  responsibility boundaries.
- Rejects malformed tool traces and tool rules with stable validation errors.
- Includes a 33-case evaluation set with stable IDs across nine categories.
- Separates outcome success from evaluator fixture conformance through an
  explicit boolean `expected_success` contract on all 33 benchmark cases.
- Produces deterministic JSON and Markdown Benchmark Reports with dimension
  averages, category breakdowns, failure analysis, and explicit unavailable
  metrics when latency/cost data is absent.
- Applies configurable Regression Gate thresholds independently of the legacy
  runner. The default gate requires evaluator conformance of 1.0 and does not
  gate the adversarial corpus on outcome success.
- Prints per-case results and an average score through the CLI.
- Returns CLI exit code 0 only when all cases pass, otherwise exit code 2.
- Optionally writes a UTF-8 Markdown summary, compatibility case table, and
  dimension-evidence table, creating parent directories as needed.
- Has pytest coverage for scoring behavior, failure reasons, Markdown reporting,
  responsibility isolation, aggregation, malformed cases, runner exit behavior,
  and the runner-to-reporter dependency boundary.

### Explicit gaps

- The 33-case Harness Benchmark still supplies `actual` data directly by design.
  The separate 10-case project 03 Integration Benchmark executes the real 03
  runtime and dynamically constructs `actual` through a thin adapter.
- Tool traces, `policy_violation`, and `verified` are still supplied observations;
  the harness does not independently collect their evidence provenance.
- Project 03 verification currently proves only a deterministic non-null metric
  result signal, not production-grade independent business validation or
  evidence provenance.
- CI has not been added because the repository still lacks the intended
  two-stage commit history.

### Verified 33-case benchmark

- Total cases: 33
- Outcome success rate: 0.242424 (8/33)
- Evaluator conformance rate: 1.000000 (33/33)
- State average: 0.787879
- Policy average: 0.545455
- Verification average: 0.818182
- Overall average: 0.745455
- Latency metrics: not available
- Cost metrics: not available

## 03-governed-mysql-data-agent

- Its README describes a governed data agent with a semantic layer, query safety,
  pre-execution validation, and evidence. The checked-in demo defaults to SQLite,
  and a MySQL schema file is present.
- Its current runtime chain is `question -> resolve_metric -> validate_sql ->
  SQLite execute -> verify_evidence -> result`. Unknown metrics stop after
  resolution; standalone policy evaluation stops after `validate_sql`.
- It now emits only the stages actually reached in a deterministic `trace`.
- Successful metric-query verification checks that the returned evidence has a
  non-null value under the resolved metric key. This is a real program check but
  remains weaker than independent production verification.
- The project remains independently runnable and does not import project 00.

### Verified 10-case real integration baseline

- Actual source: dynamically executed project 03 runtime; no fixture contains
  `actual`
- Total cases: 10
- Outcome success rate before required-dimension correction: 0.500000 (5/10)
- Outcome success rate after correction: 1.000000 (10/10)
- Evaluator conformance rate: 1.000000 (10/10)
- State average: 1.000000
- Policy average: 1.000000
- Verification average: 1.000000 across the five cases where it is applicable
- Overall average: 1.000000
- Categories: metric success, clarification, policy allowed, policy blocked

## Remaining after Phase E

Project 00 has no remaining independent framework capability gap. Future
evaluation work must be driven by a reproducible bad case from the real project
03 runtime. Separately, CI may be considered after the intended Git history is
created and recurring automation has demonstrated maintenance value.
