# Current Repository State

Verified on: 2026-08-28 (Asia/Shanghai)

This file records only facts checked in the current workspace. It is a baseline,
not a claim that the planned v0.1 work is complete.

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

### Current capabilities

- Deterministically compares every field in a case's `expected` mapping with the
  supplied observable `actual` mapping.
- Applies the current v0 weights: State 0.6, Policy 0.2, Verification 0.2.
- Requires all three checks and a score of 1.0 for case success.
- Prints per-case results and an average score through the CLI.
- Returns CLI exit code 0 only when all cases pass, otherwise exit code 2.
- Optionally writes a UTF-8 Markdown summary and case report, creating parent
  directories as needed.
- Has pytest coverage for scoring behavior, failure reasons, Markdown reporting,
  runner exit behavior, and the runner-to-reporter dependency boundary.

### Explicit gaps

- Cases supply `actual` data directly; the harness does not execute an agent or
  independently collect observable evidence.
- State, Policy, and Verification are not yet emitted as explicit dimensional
  results. Policy is currently a `policy_violation` flag, and Verification is a
  `verified` boolean rather than evidence validation.
- There is no tool-sequence evaluator, larger benchmark set, JSON benchmark
  report, automated regression gate, or integration with project 03.

## 03-governed-mysql-data-agent

- Its README describes a governed data agent with a semantic layer, query safety,
  pre-execution validation, and evidence. The checked-in demo defaults to SQLite,
  and a MySQL schema file is present.
- Project 03 was not modified in this baseline. Its behavioral tests were not run
  as part of the focused 00 baseline; repository validation did parse its Python
  sources and JSON files where applicable.

## Next-stage target: 00 v0.1

The next stage remains intentionally unimplemented:

1. Make State, Policy, and Verification explicit dimensional evaluation results.
2. Add tool sequence evaluation.
3. Build a representative benchmark and regression gate.
4. Connect the stabilized evaluation contract to
   `03-governed-mysql-data-agent` only after the preceding pieces are verified.
