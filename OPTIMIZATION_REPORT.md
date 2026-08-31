# Repository Optimization Report

Date: 2026-08-31 (Asia/Shanghai)
Initial HEAD: `9356c14290dc747e2a31d925316cae766e0b7dcf`
Overall status: **DONE**

The selected repository changes are implemented, every runnable local check
passes, and hosted GitHub Actions reproduced the complete gate against a
disposable MySQL 8.0 service. The fixed Eval Set and benchmark score remain
unchanged, both prohibited safety classes remain zero, and the real MySQL suite
passed `8/8` with a distinct SELECT-only Agent identity.

## A. Initial State Summary

### Git and ownership boundary

- Branch/HEAD inspection started at `9356c14290dc747e2a31d925316cae766e0b7dcf`.
- The working tree was already dirty: `README.md` was modified and
  `scripts/audit_repo.py` plus `tests/test_audit_repo.py` were untracked.
- Those files were treated as user-owned work. They were preserved, audited,
  tested, and integrated into the gate; no destructive Git operation was used.
- No commit was created during the initial audit because a logically complete
  audit-gate commit would have had to claim or bundle the pre-existing
  untracked audit implementation. Final Evidence Closure later supplied
  explicit authorization; all retained changes were reviewed and committed
  without rewriting history or discarding user work.

### Architecture and delivery baseline

- The repository contains one evaluation harness, five Python/Java agent
  projects, a Spring Boot A2A starter, a deterministic repository validator,
  one unified acceptance gate, and one GitHub Actions job.
- Project 03 is the principal portfolio system: governed metric resolution,
  deterministic SQL compilation, AST policy, read-only execution, strict
  result verification, and a fixed 56-case system benchmark.
- The fixed Eval Set SHA-256 was and remains
  `FFA2D213867C1AD80F386EE2D762FD91224C215E23F91FC4A6B0A2F66675A40E`.
- Baseline benchmark: `53/56`; overall `0.946429`; verification
  `21/24 = 0.875000`; `SAFE_FAILURE=3`, `FALSE_SUCCESS=0`,
  `UNSAFE_ALLOW=0`, `OVER_BLOCK=0`.
- The three failures are intentionally fail-closed ambiguous phrases:
  `money made`, `turnover`, and `fulfilled purchases`.

### Baseline verification

| Check | Baseline result |
|---|---|
| Repository validation | PASS |
| Audit tests | 17 passed |
| Repository audit | PASS; 0 HIGH, 0 WARNING, 0 INFO |
| Acceptance-gate tests | 8 passed |
| Project 00 | 58 passed |
| Project 02 | 2 passed |
| Project 03 | 172 passed, 1 skipped, 13 subtests passed |
| Project 04 | 1 passed |
| Project 05 | 1 passed |
| Project 01 Maven tests | 2 passed |
| Project 06 Maven tests | 1 passed |
| Fixed Project 03 benchmark gate | PASS |
| Python dependency consistency | `pip check`: PASS |
| Real MySQL 8.0 integration | BLOCKED: opt-in credentials not supplied |

The default gate first reported missing Maven. That was an environment issue,
not a repository regression. Apache Maven 3.9.16 was downloaded from the
official distribution, its SHA-512 was verified, and the baseline gate then
passed.

## B. Audit Findings by Priority

### P0 — Release blocking

No confirmed P0 defect was found. The executable evidence kept both prohibited
safety classes at zero, and the unified gate did not produce a false pass when
a required command was unavailable.

### P1 — High ROI

1. **Standalone safety gate was indirect.** The fixed benchmark configuration
   enforced aggregate thresholds, while exact safety counts were asserted by a
   separate integration test. The unified CI was protected, but running the
   benchmark gate alone did not visibly or independently hard-gate
   `FALSE_SUCCESS=0` and `UNSAFE_ALLOW=0`.
2. **Repository audit was outside the acceptance graph.** The existing audit
   implementation and its tests could regress without the unified gate or CI
   noticing.
3. **CI action majors were stale.** Checkout, Python setup, and Java setup used
   older supported majors than the current stable releases selected for this
   workflow.
4. **Both Spring Boot projects used 3.3.5.** Spring Boot 3.3 open-source support
   has ended, while the current stable documentation lists 4.0.8. This upgrade
   was accepted only after clean compilation and tests succeeded on Java 21.

### P2 — Important, deliberately not expanded in this pass

1. **Strict result verification is structural, not independently semantic.**
   It proves a unique finite numeric result with the expected key, but does not
   independently prove that the SQL aggregation, metric, or scope is correct.
   A second semantic engine would add considerable duplicated complexity and
   was not justified without a concrete failing case.
2. **Generic evaluator empty-expectation behavior is under-specified.** Empty
   expected mappings can pass vacuously. The fixed Project 03 set has no such
   case, so changing evaluator semantics without a product contract would risk
   unrelated behavior.
3. **Real MySQL evidence was initially historical.** Final Evidence Closure
   resolved this gap with a hosted disposable MySQL 8.0.46 service and a new
   `8/8` least-privilege run.

### P3 — Polish and evidence quality

- Test-count and gate documentation had drifted and did not describe the audit
  checks or the direct safety invariant output.
- The local interpreter is Python 3.14.6 rather than the workflow's Python
  3.12. The code passed locally, but this is not a substitute for a live CI run.
- Docker is unavailable locally; no containerized MySQL fallback was possible.

### Negative audit evidence

The deterministic audit found no tracked cache/build artifacts, large tracked
files, high-confidence secrets, technical-debt markers, dependency declaration
conflicts, broken local documentation references, or missing project/test
structure.

## C. Changes Implemented

### 1. Risk-weighted benchmark safety classification

`00-agent-eval-harness/src/integration_benchmark.py` now:

- produces mutually exclusive `SAFE_FAILURE`, `FALSE_SUCCESS`, `OVER_BLOCK`,
  `UNSAFE_ALLOW`, and `OTHER` classifications;
- includes counts and case IDs in JSON and Markdown reports;
- prints the classification in normal benchmark output;
- hard-fails `--gate` whenever either `FALSE_SUCCESS` or `UNSAFE_ALLOW` is
  non-zero, independently of aggregate thresholds.

Tests cover a synthetic false success and unsafe allow, exact classification of
the fixed baseline, deterministic report serialization, and the passing safety
gate.

### 2. Audit integrated into the acceptance graph

`scripts/acceptance_gate.py` now requires both:

- `python -m pytest -q tests/test_audit_repo.py`
- `python scripts/audit_repo.py`

The acceptance-gate unit suite asserts that neither check can silently disappear
from the constructed check list.

### 3. Supported CI action majors

- `actions/checkout`: `v4` → `v7`
- `actions/setup-python`: `v5` → `v7`
- `actions/setup-java`: `v4` → `v5`

These selections follow the official release/documentation pages. Setup Java
v5 was chosen because the project documentation identifies v6 as development,
not the latest stable release.

### 4. Spring Boot upgrade, retained conditionally on evidence

- Project 01: Spring Boot `3.3.5` → `4.0.8`
- Project 06: Spring Boot `3.3.5` → `4.0.8`

Both projects passed `mvn clean test` on Java 21 after the upgrade, including
fresh compilation. One minimal `@SpringBootTest` was added per application;
the logs prove that both Spring Boot 4.0.8 ApplicationContexts actually start.

### 5. Disposable real MySQL CI evidence

The Ubuntu hosted job now provisions `mysql:8.0.46` with temporary, public-test
credentials. It reuses Project 03's `setup_mysql.py` to create and seed the
schema, creates a separate `data_agent_ro` runtime identity, revokes its prior
privileges, and grants only `SELECT` on `data_agent.*`. The unified gate runs
with `--with-mysql`; no GitHub Secret or second initialization system was added.

### 6. Documentation and reproducibility

- The root README now states that audit tests and the audit are mandatory
  acceptance checks.
- Project 03 documentation explains the direct safety invariant gate.
- `CURRENT_STATE.md` records the new test count and verified safety behavior.
- `OPTIMIZATION_PRD.md` captures the pre-implementation problem statement,
  goals, non-goals, fact/assumption boundary, candidate ROI decisions, and
  acceptance criteria.

## D. Changes Rejected or Deferred

| Candidate | Decision | Evidence-based reason |
|---|---|---|
| Upgrade `sqlglot` 30.13.0 → 30.17.0 | Rejected for this pass | No failing parser/policy case; a safety-sensitive parser upgrade needs targeted compatibility evidence, not freshness alone. |
| Upgrade MySQL Connector/Python 9.7.0 → 26.7.0 | Rejected for this pass | Major version jump and real MySQL verification was blocked. |
| Redesign strict result verification | Deferred | No concrete regression; independent semantic verification would duplicate the compiler/catalog and raise maintenance cost. |
| Change empty-expected evaluator semantics | Deferred | No fixed benchmark exposure and no explicit desired contract. |
| Add more CI jobs/matrices | Deferred | The single unified gate is currently clear and fast; a matrix would add cost before a demonstrated compatibility need. |
| Change Eval Set or relax thresholds | Rejected | Would compromise comparability and could hide safety regressions. |
| Large architectural rewrite | Rejected | Existing boundaries are coherent and all available tests pass. |

## E. Test Evidence

### Final unified acceptance command

```powershell
$env:PATH = '<verified Apache Maven 3.9.16 bin>;' + $env:PATH
python scripts/acceptance_gate.py
```

Result: `FINAL RESULT: PASS`

| Required check | Final result |
|---|---|
| Repository validation | PASS |
| Repository audit tests | 17 passed |
| Repository audit | PASS; zero findings |
| Acceptance-gate tests | 9 passed |
| Project 00 | 59 passed |
| Project 02 | 2 passed |
| Project 03 | 172 passed, 1 skipped, 13 subtests passed |
| Project 04 | 1 passed |
| Project 05 | 1 passed |
| Project 01 | 3 tests; BUILD SUCCESS; context started |
| Project 06 | 2 tests; BUILD SUCCESS; context started |
| Project 03 benchmark gate | PASS |

Additional focused evidence:

- `python -m pytest -q tests/test_integration_03.py`: 9 passed.
- Project 01 `mvn clean test`: 3 tests, BUILD SUCCESS; Spring Boot 4.0.8
  context started.
- Project 06 `mvn clean test`: 2 tests, BUILD SUCCESS; Spring Boot 4.0.8
  context started.
- `git diff --check`: PASS.
- Maven 3.9.16 download SHA-512: verified against the official checksum.

### Hosted GitHub Actions evidence

- Workflow: [CI Regression Gate run 33362031707](https://github.com/1yu-an/evaluation-first-governed-data-agent/actions/runs/33362031707)
- Evidence commit: `67986697a55537f4ebc463425c886fa65228c5d2`
- Overall/job status: `success`; every recorded step succeeded.
- Hosted toolchain: Python `3.12.14`, OpenJDK `21.0.12.1`, Apache Maven
  `3.9.16`.
- MySQL service: `mysql:8.0.46`, healthy and disposed after the job.
- Effective Agent grants: `USAGE` on `*.*` plus `SELECT` on
  `data_agent.*`; setup identity remained `root`, runtime identity was
  `data_agent_ro`.
- Real MySQL integration: `8 passed in 0.48s`. The suite verifies SELECT,
  directly rejected INSERT/UPDATE/DELETE, scalar cardinality, exact grants,
  and SQLite/MySQL evidence parity.
- Hosted unified result: `FINAL RESULT: PASS`.

Coverage boundary:

- **Real MySQL integration — NOT RUN LOCALLY.** No local dedicated credentials
  were invented or reused; the equivalent existing suite ran and passed in the
  disposable hosted environment.
- **Dedicated SCA/vulnerability scanner — NOT RUN.** No configured scanner or
  lockfile-backed SCA workflow was present. Dependency consistency was checked
  with `pip check`, and version decisions used official lifecycle sources.

## F. Benchmark Before and After

The optimization improves the strength and observability of the gate, not the
score. The frozen cases and expected outputs were not changed.

| Metric | Before | After |
|---|---:|---:|
| Cases | 56 | 56 |
| Successful cases | 53 | 53 |
| Failed cases | 3 | 3 |
| Outcome success | 0.946429 | 0.946429 |
| Evaluator conformance | 0.946429 | 0.946429 |
| State average | 0.946429 | 0.946429 |
| Policy average | 0.946429 | 0.946429 |
| Verification average | 0.875000 | 0.875000 |
| Overall average | 0.946429 | 0.946429 |
| SAFE_FAILURE | 3 | 3 |
| FALSE_SUCCESS | 0 | 0 |
| OVER_BLOCK | 0 | 0 |
| UNSAFE_ALLOW | 0 | 0 |
| OTHER | not emitted | 0 |
| Direct safety hard gate | No | Yes |

Final gate output includes:

```text
REGRESSION GATE PASS
SAFETY INVARIANTS PASS
FALSE_SUCCESS=0 cases=none
UNSAFE_ALLOW=0 cases=none
```

## G. Remaining Risks

1. Treat future `sqlglot` upgrades as safety-sensitive and add parser-policy
   regression cases for any syntax behavior that changes.
2. Define an explicit product contract before changing empty expected mappings
   or adding semantic verification beyond the existing structural contract.
3. The Spring Boot tests prove context startup but not deployed HTTP behavior.
   Add broader tests only if these examples become deployment targets.

## H. Portfolio Impact

- **Production maturity:** safety invariants are first-class machine gates, not
  only prose or indirect test assertions.
- **Reproducibility:** one root command now covers validation, audit, all local
  language suites, and the fixed system benchmark.
- **Technical depth:** reports expose mutually exclusive failure-risk classes
  with case IDs, making safety claims independently reviewable.
- **Maintainability:** supported CI and Spring Boot lines reduce lifecycle risk
  without broadening the architecture.
- **Interview signal:** the unchanged score demonstrates that the work improves
  evidence quality and failure policy instead of gaming the benchmark.

## I. Final Repository State

- All available required local checks: **PASS**.
- Fixed Eval Set hash: unchanged.
- Benchmark result: `53/56`; `SAFE_FAILURE=3`; `OVER_BLOCK=0`.
- `FALSE_SUCCESS=0`: preserved and directly gated.
- `UNSAFE_ALLOW=0`: preserved and directly gated.
- Real MySQL integration: **PASS, 8/8** in disposable MySQL 8.0.46.
- Live hosted CI: **PASS** for implementation commit `6798669`.
- Local Acceptance Gate: **PASS**; local real MySQL accurately marked
  `NOT RUN LOCALLY`.
- Retained changes were committed and pushed without force, history rewrite,
  or deletion of user work.

### Official lifecycle sources used

- [Spring Boot 3.3.13 release and OSS support end](https://spring.io/blog/2025/06/19/spring-boot-3-3-13-available-now/)
- [Spring Boot stable documentation](https://docs.spring.io/spring-boot/)
- [actions/checkout releases](https://github.com/actions/checkout/releases)
- [actions/setup-python releases](https://github.com/actions/setup-python/releases)
- [actions/setup-java releases](https://github.com/actions/setup-java/releases)
- [setup-java advanced usage and stable-major guidance](https://github.com/actions/setup-java/blob/main/docs/advanced-usage.md?plain=1)
- [Apache Maven downloads and checksums](https://maven.apache.org/download.cgi)
