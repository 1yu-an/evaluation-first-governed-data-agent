# Repository Optimization PRD

Verified on: 2026-08-31 (Asia/Shanghai)

## Problem

The repository's frozen Project 03 implementation is currently correct against
its declared 56-case benchmark and preserves the two non-negotiable safety
invariants (`FALSE_SUCCESS=0`, `UNSAFE_ALLOW=0`). The highest-value work is not
new Agent functionality. It is closing small verification and delivery gaps so
that the repository proves those properties directly, reproducibly, and with
less reliance on readers knowing which overlapping test provides which guard.

Three concrete gaps have evidence:

1. The Project 03 integration test asserts safety classifications, but the
   standalone Benchmark report and Regression Gate expose only aggregate rates.
   A score-preserving exchange between a low-risk success and a high-risk failure
   can therefore pass the standalone gate even though the complete repository
   Acceptance Gate would still fail in the 00 integration test.
2. The existing Repository Audit v1 and its 17 tests are not included in the
   unified Acceptance Gate, so the current CI does not execute this new control.
3. The CI workflow uses old major versions of the official GitHub Actions, and
   both Java projects inherit from an end-of-open-source-support Spring Boot
   line.

## Goal

Make a small set of evidence-backed changes that:

- makes Project 03 safety classifications machine-readable and directly gated;
- makes the existing static Repository Audit part of the single local/CI
  Acceptance Gate;
- moves the CI workflow to current stable official Action major versions;
- moves the two small Java examples off the unsupported Spring Boot 3.3 line if
  the current test/build surface continues to pass;
- preserves the fixed 56-case Eval Set and the frozen Project 03 behavior;
- leaves `FALSE_SUCCESS=0` and `UNSAFE_ALLOW=0` as hard acceptance conditions.

## Non-Goals

- Do not add metrics, aliases, filters, frameworks, databases, caches, queues, or
  LLM SDKs.
- Do not modify the fixed 56-case Eval Set or optimize for 56/56.
- Do not redesign the Agent, semantic plan, compiler, SQL policy, executor, or
  result-verification architecture.
- Do not claim that strict result-shape verification proves SQL business
  semantics.
- Do not make real MySQL integration mandatory in default CI; it requires an
  externally prepared database and dedicated credentials.
- Do not broadly reformat the repository or clean unrelated prototype code.
- Do not add a dependency scanner or cache solely for architectural appearance.

## Initial Baseline

- Git HEAD: `9356c14290dc747e2a31d925316cae766e0b7dcf`.
- Pre-existing worktree changes preserved:
  - modified `README.md` (Repository Audit documentation);
  - untracked `scripts/audit_repo.py`;
  - untracked `tests/test_audit_repo.py`.
- Fixed Eval Set: 56 cases, SHA-256
  `FFA2D213867C1AD80F386EE2D762FD91224C215E23F91FC4A6B0A2F66675A40E`.
- Baseline Benchmark: 53/56 success, overall `0.946429`, verification
  `21/24 = 0.875000`, `SAFE_FAILURE=3`, `FALSE_SUCCESS=0`,
  `UNSAFE_ALLOW=0`, `OVER_BLOCK=0`.
- Repository Acceptance Gate: PASS after using a temporary, SHA-512-verified
  Apache Maven 3.9.16 runtime.
- Python suites: 00 `58 passed`; 02 `2 passed`; 03 `172 passed, 1 skipped,
  13 subtests passed`; 04 `1 passed`; 05 `1 passed`; root Acceptance Gate tests
  `8 passed`; Repository Audit tests `17 passed`.
- Java suites: 01 `2 passed`; 06 `1 passed`.
- Real MySQL integration: BLOCKED. MySQL80 is running locally, but the required
  dedicated Agent credentials and opt-in environment are absent. Docker is also
  absent.

## Findings

### Facts

- Project 03 follows the documented data flow:
  `question -> SemanticPlan -> deterministic compiler -> AST policy -> executor
  -> strict result contract -> result`.
- SQL compilation uses a finite metric catalog and fixed compiler strategies;
  filter values remain separate bound parameters.
- SQL policy parses MySQL SQL with sqlglot, rejects multiple statements, DML,
  DDL, `INTO`, and locking reads, and permits read-only SELECT/CTE queries.
- MySQL configuration rejects root/admin identity and requires a separate Agent
  account; setup tests revoke privileges before granting only SELECT.
- Strict verification proves exactly one row, exactly one expected key, numeric
  type, non-null, and finite value. It explicitly does not prove the business
  meaning of the compiled SQL.
- Adversarial tests demonstrate that a wrong metric, wrong aggregation, or
  dropped scope can still satisfy the shape-only result contract if the compiler
  is replaced with an incorrect implementation.
- The deterministic compiler and semantic-plan tests are therefore part of the
  current semantic correctness argument; verification is not an independent
  oracle.
- The 00 integration test dynamically executes Project 03, locks the Eval Set
  hash and exact baseline, and explicitly asserts all four safety classes.
- The standalone Regression Gate configuration contains only minimum aggregate
  score/rate thresholds.
- The unified Acceptance Gate currently does not run Repository Audit v1 or its
  test module.
- `pip check` reports no broken requirements. `pytest==9.1.1` is current;
  `sqlglot==30.13.0` trails `30.17.0`; `mysql-connector-python==9.7.0` trails a
  new versioning line (`26.7.0`).
- Both Java POMs use Spring Boot `3.3.5`. Spring's official release notice states
  that 3.3.x open-source support ended with 3.3.13 and recommends upgrading.
- On 2026-08-31 the official stable Action majors are `actions/checkout@v7`,
  `actions/setup-python@v7`, and `actions/setup-java@v5`; the workflow uses
  v4, v5, and v4 respectively.
- No Git-tracked cache/build artifacts, high-confidence secrets, broken local
  documentation links, duplicate direct dependencies, or missing project test
  roots were found by Repository Audit v1.

### Assumptions

- GitHub-hosted `ubuntu-latest` runners satisfy the minimum runner requirement
  of the current official Action majors.
- The existing Repository Audit implementation is intentional user work for
  this optimization effort and should be completed/integrated rather than
  discarded.
- Spring Boot 4.0.x is a lower-risk supported target than the newer 4.1.x line
  for these small Java examples, while still leaving the unsupported 3.3 line.

### Inferences

- Explicit safety classification in the Benchmark report improves both
  fail-closed regression control and portfolio explainability without changing
  Agent behavior.
- Running Repository Audit v1 inside the Acceptance Gate closes a real test
  discovery gap at low incremental CI cost.
- Updating official Action majors has high maintenance ROI and minimal
  repository blast radius.
- Updating Spring Boot is justified by support status, not by novelty. Its risk
  is bounded but not eliminated by the current three Java tests, so it must be
  accepted only after compile/test and repository regression evidence.

### Unknowns

- Real MySQL behavior cannot be revalidated without dedicated runtime and admin
  credentials. Historical 8/8 evidence remains documented but is not a result
  of this run.
- Local Python is 3.14.6 rather than CI's 3.12; CI compatibility is supported by
  the existing workflow/history but cannot be reproduced with a local 3.12
  interpreter on this host.
- No live GitHub Actions run can be observed from this local workspace.
- A full software-composition vulnerability database scan was not available;
  support status, declared versions, package-index state, and local build/test
  evidence are used instead.
- The Java tests are compile/unit acceptance evidence, not comprehensive HTTP,
  persistence, or migration coverage.

## Candidate Improvements

### P1 — Add explicit Project 03 safety classification and hard safety gate

| Item | Assessment |
|---|---|
| Problem | Standalone Benchmark output/gating exposes aggregate rates but not the safety classes that define acceptable failure. |
| Evidence | `03_regression_gate.json` contains only six minimum rate/score thresholds; classification logic exists only inside an integration test. |
| Benefit | Prevents score compensation from hiding `FALSE_SUCCESS` or `UNSAFE_ALLOW`; makes the safety argument machine-readable and reviewer-visible. |
| Cost | Small, localized additions to the Project 03 integration benchmark plus focused tests and documentation. |
| Risk | Misclassification if rules diverge from the existing tested definitions. Mitigate by extracting the current definitions and locking baseline counts. |
| Complexity | Low to medium. |
| Portfolio Value | High: demonstrates risk-weighted Agent evaluation rather than score-only benchmarking. |
| Recommendation | IMPLEMENT. Keep classification Project-03-specific; do not pollute the generic benchmark evaluator. Gate `FALSE_SUCCESS` and `UNSAFE_ALLOW` at zero. |

### P1 — Integrate Repository Audit v1 into the unified Acceptance Gate

| Item | Assessment |
|---|---|
| Problem | The static audit and its tests can regress without affecting current CI. |
| Evidence | `build_checks()` includes only `tests/test_acceptance_gate.py` at the root and has no audit command. |
| Benefit | One command/CI job covers repository hygiene, secret-risk heuristics, dependency declarations, docs references, and audit tests. |
| Cost | Two Check entries plus Acceptance Gate test updates. |
| Risk | Advisory warnings must not become accidental failures; the audit already exits nonzero only for HIGH findings. |
| Complexity | Low. |
| Portfolio Value | High: closes the gap between a documented control and enforced CI evidence. |
| Recommendation | IMPLEMENT. Run audit tests before the audit command, with deterministic read-only behavior. |

### P1 — Upgrade official GitHub Action majors

| Item | Assessment |
|---|---|
| Problem | Workflow uses old Node-runtime Action generations. |
| Evidence | Official releases show checkout v7, setup-python v7, setup-java v5 as current stable majors; workflow uses v4/v5/v4. |
| Benefit | Removes stale runtime/dependency exposure and keeps CI on supported Action generations. |
| Cost | Three YAML version edits. |
| Risk | Hosted-runner compatibility; low on `ubuntu-latest`, and no special checkout behavior is used. |
| Complexity | Low. |
| Portfolio Value | Medium to high: current, explainable CI maintenance. |
| Recommendation | IMPLEMENT. Preserve Python 3.12, Java 21, permissions, and existing cache behavior. |

### P1 — Move Java examples from Spring Boot 3.3.5 to 4.0.8

| Item | Assessment |
|---|---|
| Problem | Both Java projects inherit from an end-of-open-source-support line. |
| Evidence | Spring's official 3.3.13 notice marks 3.3.x OSS support ended; 4.0.8 is listed as a stable line. |
| Benefit | Restores a supported dependency baseline without introducing a new framework. |
| Cost | Two parent-version edits plus compile/test/full-gate verification. |
| Risk | Major-version behavior changes are not fully covered by the three Java unit tests. |
| Complexity | Low edit cost, medium validation risk. |
| Portfolio Value | Medium: avoids presenting an obviously unsupported Spring baseline. |
| Recommendation | IMPLEMENT CONDITIONALLY. Keep only if both projects compile/test and the complete gate passes; otherwise revert these two edits and record rejection. |

### P2 — Upgrade sqlglot from 30.13.0 to 30.17.0

| Item | Assessment |
|---|---|
| Problem | The AST policy dependency is four patch/minor releases behind. |
| Evidence | Official package index reports 30.17.0 current. No specific required fix or vulnerability was identified. |
| Benefit | Possible parser fixes. |
| Cost | One pin change and full policy/adversarial regression. |
| Risk | Parser/AST behavior changes affect a safety boundary. |
| Complexity | Low. |
| Portfolio Value | Low without a linked defect. |
| Recommendation | REJECT for this round. Passing safety tests and no concrete defect make churn higher ROI risk than benefit. |

### P2 — Upgrade mysql-connector-python to 26.7.0

| Item | Assessment |
|---|---|
| Problem | Declared connector is behind the newest versioning line. |
| Evidence | Official package index reports 26.7.0 current. |
| Benefit | Current driver fixes and support. |
| Cost | Pin change plus real MySQL validation. |
| Risk | Real MySQL integration is blocked, so prepared-cursor and Decimal behavior cannot be verified end to end. |
| Complexity | Low edit, unavailable required validation. |
| Portfolio Value | Low if unverified. |
| Recommendation | REJECT until the opt-in MySQL environment is available. |

### P2 — Reject empty `expected` mappings in the generic evaluator

| Item | Assessment |
|---|---|
| Problem | An empty expected mapping makes State vacuously pass. |
| Evidence | A dedicated evaluator test documents this behavior. The fixed Project 03 set does not use empty expected mappings. |
| Benefit | Stronger generic fixture validation. |
| Cost | Contract change and fixture compatibility review across the generic harness. |
| Risk | Breaks intentional policy-only or verification-only use cases unless the required-dimension contract is redesigned. |
| Complexity | Medium. |
| Portfolio Value | Medium, but outside the current proven risk path. |
| Recommendation | REJECT for this round; document as a remaining generic harness risk. |

### P3 — Build independent semantic SQL verification

| Item | Assessment |
|---|---|
| Problem | Shape-only verification cannot independently prove metric, aggregation, or scope semantics. |
| Evidence | Three adversarial tests deliberately demonstrate this limitation. |
| Benefit | Stronger defense in depth if an independent oracle were reliable. |
| Cost | High; likely duplicates compiler/catalog semantics or creates a second complex framework. |
| Risk | False confidence, divergent duplicate logic, feature-freeze violation. |
| Complexity | High. |
| Portfolio Value | Negative if over-engineered; current explicit limitation is more credible. |
| Recommendation | REJECT. Preserve the honest contract and deterministic compiler tests. |

## Selected Scope and Sequence

1. Add Project 03-specific safety classification to the integration report and
   direct gate; add tests proving a compensated score cannot hide
   `FALSE_SUCCESS` or `UNSAFE_ALLOW`.
2. Add Repository Audit tests and the read-only audit command to the unified
   Acceptance Gate; update its orchestration tests.
3. Upgrade official GitHub Action majors without changing language versions or
   job structure.
4. Conditionally update both Spring Boot parents to 4.0.8 and retain only with
   successful Maven and full repository acceptance evidence.
5. Update concise documentation only where enforcement/status claims change.

## Acceptance Criteria

- Fixed Eval Set hash remains unchanged.
- Project 03 ordinary suite passes.
- Project 00 suite passes.
- Direct Project 03 Benchmark Gate prints and enforces safety counts.
- `FALSE_SUCCESS=0` and `UNSAFE_ALLOW=0` are hard gate conditions that cannot be
  offset by other successful cases.
- Repository Audit tests and audit execution are visible in Acceptance Gate
  output and CI coverage.
- Both Java projects pass if the Spring Boot update is retained.
- Unified Acceptance Gate passes with Maven available.
- Real MySQL is reported as BLOCKED unless credentials become available.
- `git diff --check` passes and every final worktree change is explained.
