# Current Repository State

Verified on: 2026-08-28 (Asia/Shanghai)

This file records only facts checked in the current workspace. The repository
contains the baseline commit `c79a809`, the reusable evaluation/integration
commit `13027ce`, the frozen 56-case Baseline v0 commit `e2e26c9`, and the
risk-analysis documentation commit `c01d57b`. Semantic Plan Improvement v1 is
currently kept in the working tree for review and is not committed.

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
- After expanding the integration fixture to 56 cases: 57 project 00 pytest
  tests passed; project 03 remains at 6 passing tests.
- After Semantic Plan Improvement v1 and anti-overfitting review: 57 project 00
  pytest tests passed; project 03 increased from 6 to 21 passing tests.

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
  The separate 56-case project 03 Integration Benchmark executes the real 03
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

### Verified 56-case real integration baseline v0

- Actual source: dynamically executed project 03 runtime; no fixture contains
  `actual`
- Total cases: 56
- Successful / failed outcomes: 37 / 19
- Outcome success rate: 0.660714
- Evaluator conformance rate: 0.660714
- State average: 0.660714
- Policy average: 0.714286
- Verification average: 0.458333 across 24 applicable cases
- Overall average: 0.676786
- Largest failure categories: synonym/paraphrase 8, result edge 6,
  ambiguous input 3, safe SQL false rejection 2
- Full case distribution and five representative Bad Cases are recorded in
  `03-governed-mysql-data-agent/BASELINE_V0.md`.

## Remaining after Baseline v0 measurement

Project 00 has no remaining independent framework capability gap. The 19 real
03 failures are measurement evidence for future work; none were fixed in this
phase. Future changes should be driven by these reproducible Bad Cases rather
than by independent framework expansion.

Risk analysis classifies the 19 failures as 13 SAFE_FAILURE, 4 FALSE_SUCCESS,
2 OVER_BLOCK, 0 UNSAFE_ALLOW, and 0 OTHER. Resolver/Semantic is the primary
responsibility layer for 17; Policy is primary for 2; Verification contributes
to all 4 FALSE_SUCCESS cases by accepting result shape without full request
agreement. Full reasoning and priorities are in
`03-governed-mysql-data-agent/BASELINE_V0.md`.

## Semantic Plan Improvement v1 (working tree)

- Adds a minimal `SemanticPlan` with explicit `metric`, `filters`, `status`, and
  `reason` fields and no third-party dependency.
- Blocks multiple recognized metrics, explicitly vague scope wording, and
  recognized-but-unsupported region filters before SQL policy or execution.
- Preserves normal canonical and configured-alias queries.
- Does not expand synonym mappings, change the 56-case Eval Set, modify project
  00 evaluator rules, or refactor Verification.
- Anti-overfitting review replaced a benchmark-derived phrase-prefix check with
  a single-metric plus unspecified-scope-cue condition. Unseen multi-metric,
  west-region, ambiguity, and normal single-metric wording tests all pass.
- Original FALSE_SUCCESS cases change as follows: three ambiguous cases become
  successful clarification outcomes; the north-region revenue case becomes a
  SAFE_FAILURE because unsupported scope is preserved and stopped before SQL.

### Before -> after 56-case metrics

| metric | Baseline v0 | Improvement v1 |
|---|---:|---:|
| Successful outcomes | 37 | 40 |
| Failed outcomes | 19 | 16 |
| Outcome success rate | 0.660714 | 0.714286 |
| SAFE_FAILURE | 13 | 14 |
| FALSE_SUCCESS | 4 | 0 |
| OVER_BLOCK | 2 | 2 |
| UNSAFE_ALLOW | 0 | 0 |
| State average | 0.660714 | 0.714286 |
| Policy average | 0.714286 | 0.750000 |
| Verification average | 0.458333 | 0.416667 |
| Overall average | 0.676786 | 0.723214 |

The lower Verification average is expected: the north-region request no longer
executes an incorrect global query that previously received `verified=true`.
There are no new failing case IDs; the remaining 16 are a strict subset of the
Baseline v0 failures.

## Phase G — Remaining Failure Analysis (working tree)

Verified on 2026-08-29 after commits `3fa52d2` (Semantic Plan safety gate) and
`e2e94d7` (AST SQL Policy v1). This phase changes documentation only; production
code and the 56-case Eval Set remain unchanged.

- Project 03: 36 pytest tests plus 13 subtests passed.
- Project 00: 57 pytest tests passed.
- `scripts/validate_all.py`: passed.
- Real 03 Integration Benchmark: 56 total, 42 success, 14 failure, outcome
  success rate 0.750000.
- Severity: 14 SAFE_FAILURE, 0 FALSE_SUCCESS, 0 OVER_BLOCK, 0 UNSAFE_ALLOW,
  0 OTHER.
- Remaining categories: 8 synonym/paraphrase and 6 result-edge.
- First-failing responsibility: Resolver/Semantic matching 10, Semantic catalog
  3, Semantic-plan-to-SQL boundary 1. No remaining case reaches SQL Policy,
  execution, or verification.
- Independent demo-data queries reproduce all six result-edge expected values;
  dataset absence is not a primary cause.
- The 14 cases reduce to three shared gaps: fixed-vocabulary recall for eight
  supported-metric paraphrases, missing executable filter/scope compilation for
  three cases, and three absent governed aggregate definitions/operators.
- Exactly one recommended next capability is a filter-aware logical plan plus
  deterministic SQL compiler. It has higher governed-agent reuse and controls
  a higher latent wrong-scope cost than case-local synonym or aggregate patches.

The complete 14-case table, result-edge A–F classification, root-cause grouping,
priority reasoning, and rejected alternatives are recorded in
`03-governed-mysql-data-agent/BASELINE_V0.md`. No capability was implemented and
nothing has been staged or committed in Phase G.
