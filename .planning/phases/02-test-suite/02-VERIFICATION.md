---
phase: 02-test-suite
verified: 2026-04-25T00:00:00Z
status: gaps_found
score: 3/4 ROADMAP success criteria verified (15/16 must-haves verified across plans)
overrides_applied: 0
re_verification:
  previous_status: draft (Wave-4 executor self-report)
  previous_score: 3/4 SCs (executor's own assessment)
  gaps_closed: []
  gaps_remaining:
    - "ROADMAP SC #2: services + middleware coverage ≥60%"
    - "TEST-04: pytest --cov shows 60%+ on services and middleware"
  regressions: []
gaps:
  - truth: "Coverage report shows 60%+ on services and middleware packages (ROADMAP SC #2 / TEST-04)"
    status: failed
    reason: "Combined services+middleware statement+branch coverage is 32.0% (line-only 35.6%) vs. required 60%. The pytest-cov gate (--cov-fail-under=60 in pyproject.toml) FAILS on every run today, so the suite as a whole exits non-zero. Five service files account for ~1049 of the missed statements and have effectively zero coverage: refresh_employee_profiles.py (16.4%, -292), genesys_cache_db.py (11.9%, -225), compliance_checking_service.py (0.0%, -202), job_role_warehouse_service.py (14.7%, -193), job_role_mapping_service.py (13.3%, -137). D-12 explicitly scoped seed tests to the 3 hot-path files (search_orchestrator, ldap_service, genesys_service) but did NOT carve these 5 files out of the 60% gate scope (D-11 keeps the gate on all of app/services/ + app/middleware/). The plan's own must-have 04-T1 ('coverage ≥60% on app/services/ + app/middleware/') is therefore unmet."
    artifacts:
      - path: "app/services/refresh_employee_profiles.py"
        issue: "16.4% covered; 292 statements missed. No tests in tests/unit/services/. Background-job sync logic untested."
      - path: "app/services/genesys_cache_db.py"
        issue: "11.9% covered; 225 statements missed. Cache layer for Genesys data; no targeted tests."
      - path: "app/services/compliance_checking_service.py"
        issue: "0.0% covered; 202 statements missed. Job-role compliance engine; no tests written."
      - path: "app/services/job_role_warehouse_service.py"
        issue: "14.7% covered; 193 statements missed. Warehouse sync service; no tests."
      - path: "app/services/job_role_mapping_service.py"
        issue: "13.3% covered; 137 statements missed. Mapping CRUD; no tests."
      - path: "app/services/graph_service.py"
        issue: "10.2% covered; 191 statements missed. Real GraphService class is shadowed in integration tests by FakeGraphService; the real implementation never runs in the suite."
      - path: "app/services/audit_service_postgres.py"
        issue: "19.4% covered; 149 statements missed. Concrete audit service internals untested (only exercised indirectly through middleware)."
      - path: "pyproject.toml"
        issue: "Configures --cov-fail-under=60 against app.services + app.middleware; this gate currently FAILS, meaning every `make test` / `pytest tests/` invocation exits non-zero. The pre-push hook therefore blocks ALL pushes today, including pushes that introduce no test changes — the gate is functioning but the codebase cannot satisfy it."
    missing:
      - "A follow-up plan (suggested name: 02-05-coverage-closure) that adds boundary-style tests for the 5 zero/low-coverage service files (refresh_employee_profiles, genesys_cache_db, compliance_checking_service, job_role_warehouse_service, job_role_mapping_service) — collectively ~1049 missed statements; closing 50% of these would raise combined coverage from 32% to ~46% and the rest gets to ≥60%."
      - "OR an explicit, documented decision to amend D-11 / TEST-04 to scope the 60% gate more narrowly (e.g., gate only on app/middleware/ + the D-12 hot-path files). This requires a REQUIREMENTS.md amendment and an override entry — it is a contract change, not a verification fix."
      - "Either way: until one of the above lands, the pre-push hook will block every push. Recommend NOT lowering --cov-fail-under in pyproject.toml as a quick fix (executor correctly resisted this); the right answer is more tests OR a scope amendment."
human_verification:
  - test: "Run `git push` against any branch from a fresh clone with `git config core.hooksPath .githooks` set, with no test changes. Confirm the push is blocked by the coverage gate (FAIL Required test coverage of 60% not reached. Total coverage: 31.99%)."
    expected: "Push blocked, exit non-zero. This confirms the gate is live AND that today's main branch cannot be pushed without --no-verify until the coverage gap is closed."
    why_human: "Confirms the gate behaves the same on a real developer workstation (with their own .env, Docker daemon, and git config) as it did in Wave-4's programmatic simulation. The simulation skipped the actual `git push --dry-run` step per AUTO-MODE."
  - test: "From a fresh clone, run `pip install -r requirements.txt -r requirements-dev.txt` then `pytest tests/ -v`. Confirm 36 pass + 4 strict-xfail + coverage gate FAILS."
    expected: "Suite green for tests; gate red for coverage. Reproduces the documented state on a clean machine (verifies requirements files are complete and that no test depends on uncommitted local state)."
    why_human: "Verifies the install path works end-to-end on a workstation with Docker available; the verifier cannot spin up a fresh clone."
---

# Phase 2: Test Suite — Verification Report

**Phase Goal:** Developers can run a full test suite that covers services and middleware, with mocked external APIs, preventing regressions before any auth/DB refactor or write operations ship.

**Verified:** 2026-04-25
**Status:** gaps_found
**Re-verification:** Yes — supersedes Wave-4 executor's draft VERIFICATION.md

This report is the canonical verification for Phase 2. It augments Wave 4's
draft (which was structurally a run report) with goal-backward verification
against ROADMAP success criteria, REQUIREMENTS TEST-01..04, and the four
plans' frontmatter must-haves.

---

## ROADMAP §Phase 2 Success Criteria

| # | Success Criterion | Status | Evidence |
|---|------------------|--------|----------|
| 1 | `pytest tests/ -v` runs to completion without real LDAP/Graph/Genesys calls | PASS | `tests/conftest.py` registers `FakeLDAPService` / `FakeGraphService` / `FakeGenesysService` at the DI-container layer; `app/__init__.py:141,163,184,193,201` gates background threads + token-refresh + Genesys cache warmup on `os.environ.get("TESTING") or app.config.get("TESTING")`. 40 tests run in 18.71s — no network I/O. Fakes implement `ISearchService` / `ITokenService` (D-04). |
| 2 | Coverage report shows 60%+ on services and middleware packages | **FAIL** | Combined statement+branch coverage **32.0%** (line-only 35.6%); middleware 56.2%, services 33.0%. `--cov-fail-under=60` gate in `pyproject.toml` fires `FAIL Required test coverage of 60% not reached. Total coverage: 31.99%`. Five service files (refresh_employee_profiles, genesys_cache_db, compliance_checking_service, job_role_warehouse_service, job_role_mapping_service) account for ~1049 missed statements; D-12 only seed-tested 3 hot-path files but D-11 left the gate scope across all of app/services/. |
| 3 | Authentication middleware pipeline and full search flow verified by integration tests | PASS | `tests/integration/test_auth_pipeline.py` (6 tests, all passing) covers existing-user-retained, missing-header, insufficient-role, admin-can-reach-admin, request-id-in-logs, audit-trace. `tests/integration/test_search_flow.py` (9 tests: 5 passing + 4 strict-xfailed against pre-existing production bugs) exercises real `SearchOrchestrator` / `ResultMerger` / middleware end-to-end against fakes. |
| 4 | A failing test blocks a developer from merging | PASS | `.githooks/pre-push` (executable, `set -euo pipefail`, calls `make test`); `Makefile:test` calls `pytest -x`. Wave-4 programmatically verified: green path → exit 0 → push permitted; red path → exit 1 → push blocked; coverage-drop path → exit non-zero → push blocked. README.md §Testing documents the one-line installer (`git config core.hooksPath .githooks`) and `git push --no-verify` emergency escape (D-09). |

**Score: 3/4 success criteria PASS.**

---

## REQUIREMENTS Coverage (TEST-01..TEST-04)

| Requirement | Plan(s) | Description | Status | Evidence |
|-------------|---------|-------------|--------|----------|
| TEST-01 | 02-01, 02-02, 02-03 | Developer can run `pytest tests/ -v` and get passing unit tests for all service classes | SATISFIED with caveat | Suite runs to completion with 36 passes + 4 strict-xfailed (production bugs). Unit tests exist for the 3 hot-path services (D-12: search_orchestrator, ldap_service, genesys_service). Acceptance text says "all service classes" — strictly read, this is unsatisfied (12 of 17 services have no unit tests). Consistent with D-12's deliberate scoping but worth flagging. |
| TEST-02 | 02-02 | External APIs (LDAP, Graph, Genesys) are mocked at container level in test fixtures | SATISFIED | `tests/fakes/{fake_ldap_service,fake_graph_service,fake_genesys_service}.py` exist; `tests/conftest.py` overrides `app.container.register("ldap_service", ...)` etc. (D-04, D-05). 18.71s wall time across 40 tests confirms no network I/O. |
| TEST-03 | 02-03 | Integration tests verify authentication middleware pipeline and search flow end-to-end | SATISFIED | `tests/integration/test_auth_pipeline.py` (6 tests covering D-13's full chain) + `tests/integration/test_search_flow.py` (9 tests covering D-14's e2e merge). Real middleware + orchestrator + merger exercised against fakes. |
| TEST-04 | 02-04 | Coverage report generated with `pytest --cov=app` showing 60%+ on services and middleware | **BLOCKED** | Coverage report IS generated (term-missing + html via pyproject.toml `--cov-report` flags). 60% threshold NOT met: combined 32.0% (line-only 35.6%) vs. required 60%. Acceptance text says "showing 60%+" — read literally, this requirement is not satisfied. Gate is correctly configured (`--cov-fail-under=60` in pyproject.toml is unchanged) and correctly fails. |

**No orphaned requirements** — all four TEST-* IDs map to at least one plan; no requirement listed under Phase 2 in REQUIREMENTS.md is unaccounted for in plan frontmatter.

---

## Plan-Level Must-Haves (15 of 16 verified)

### Plan 02-01: Test Infra Scaffolding (3/3 truths PASS)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Developer can run `make test` and pytest is invoked with coverage gating enabled | PASS | `Makefile` target `test` shells `pytest -x`; pyproject.toml addopts injects `--cov-fail-under=60`. |
| 2 | Production install does NOT pull pytest, factory-boy, testcontainers, ruff, or mypy | PASS | Grep of `requirements.txt` for the dev tools returns zero matches; `requirements-dev.txt` contains pytest>=8, pytest-cov>=5, pytest-mock>=3.14, factory-boy>=3.3, testcontainers[postgres]>=4, beautifulsoup4>=4.12, ruff, mypy. |
| 3 | Pre-push git hook exists at `.githooks/pre-push` that calls `make test` and exits non-zero on failure | PASS | File exists, mode 100755, body invokes `make test` under `set -euo pipefail`. Programmatically verified for green/red/coverage-drop paths. |

### Plan 02-02: Fixtures, Fakes & Factories (6/6 truths PASS)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `app.config['TESTING']` is True when conftest creates the app, and no background threads start | PASS | `app/__init__.py:184,193,201` — three gated `if not (TESTING)` checks before `.start()` on token_refresh, employee_profiles refresh, cache_cleanup. Plan also added `os.environ.get("TESTING")` checks (per deferred-items.md auto-fix #3) so the gate fires before app.config is set. |
| 2 | Test session boots a single ephemeral PostgreSQL container, applies create_tables.sql + analyze_tables.sql | PASS | `tests/conftest.py` uses `testcontainers[postgres]`; loads SQL per D-02. Wave-4 confirmed Docker required and 18.71s end-to-end is consistent with one shared container. |
| 3 | Each test runs inside a SAVEPOINT that rolls back at teardown — no cross-test data leak | PARTIAL (override candidate) | Per `deferred-items.md` auto-fix #2, the SAVEPOINT pattern broke under sequential commits in integration tests; replaced with TRUNCATE-on-teardown for `db_session`. Achieves the same goal (no cross-test leak) via a different mechanism. **This deviates from D-03**. Consider adding a verification override accepting TRUNCATE as the chosen isolation strategy. |
| 4 | FakeLDAPService / FakeGraphService / FakeGenesysService each implement the same interface as real services | PASS | Files exist in `tests/fakes/`; integration tests run real orchestrator against them and produce real-shaped results. |
| 5 | Container override fixture replaces real services with fakes via `app.container.register(...)` | PASS | `tests/conftest.py` performs container overrides per D-04. |
| 6 | factory_boy factories for User, ApiToken, JobCode, SystemRole | PASS | `tests/factories/{user,api_token,job_code,system_role}.py` all present. |

### Plan 02-03: Targeted & Integration Tests (5/5 truths PASS)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `pytest tests/unit/services/test_search_orchestrator.py -v` passes (concurrent merge, multiple_results, timeout, too_many_results) | PASS | File exists; search_orchestrator.py at 78.6% — best-covered service file. |
| 2 | `pytest tests/unit/services/test_ldap_service.py -v` passes (search_user happy/empty/multiple, test_connection failure) | PASS | File exists; ldap_service.py at 54.6%; happy/empty/multiple/exception paths covered per Wave-4 per-file table. |
| 3 | `pytest tests/unit/services/test_genesys_service.py -v` passes (search_user, refresh_token, ApiToken row written) | PASS | File exists; genesys_service.py at 28.7% — boundaries covered, internals not. |
| 4 | `pytest tests/integration/test_auth_pipeline.py -v` passes (4+ test cases per D-13) | PASS | 6 tests, all passing. |
| 5 | `pytest tests/integration/test_search_flow.py -v` passes (~6-8 tests per D-14) | PASS | 9 tests: 5 passing + 4 strict-xfailed. The strict-xfailed tests cover the production bugs documented in deferred-items.md; they will flip to XPASS (and fail strict) when bugs are fixed. |

### Plan 02-04: Coverage Gate & Docs (4/5 truths PASS, 1 FAIL)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running `pytest tests/ -v` from a fresh install produces a passing run with coverage ≥60% on services + middleware | **FAIL** | Suite passes (36 + 4 xfailed) BUT coverage gate fails at 32.0% combined vs. 60% required. The "passing run with coverage ≥60%" composite condition is not met today. This is the same gap as ROADMAP SC #2. |
| 2 | Running `make test` produces the same result as `pytest tests/ -v` | PASS | Makefile `test` target calls `pytest -x`, picking up the same pyproject.toml addopts. |
| 3 | Running `git push` on a branch with a deliberately broken test is BLOCKED | PASS | Wave-4 programmatically verified red-path exit 1 → `set -euo pipefail` aborts → push blocked. |
| 4 | README.md documents the one-line installer (`git config core.hooksPath .githooks`) and the `make test` target | PASS | README.md §Testing contains both. |
| 5 | VERIFICATION.md records the actual coverage percentage achieved (per-file table) | PASS | This document — see "Per-File Coverage" section preserved from Wave-4's draft. |

---

## Per-File Coverage (services + middleware) — preserved from Wave 4

```
app\middleware\audit_logger.py                   19      4      0      0  78.9%
app\middleware\auth.py                           98     43     28      4  51.6%
app\middleware\authentication_handler.py         22      3      4      1  84.6%
app\middleware\csrf.py                           85     54     18      1  31.1%
app\middleware\errors.py                         25     21      2      0  14.8%
app\middleware\request_id.py                     27      1      4      2  90.3%
app\middleware\role_resolver.py                  39      9     12      5  72.5%
app\middleware\security_headers.py               12     12      0      0   0.0%
app\middleware\session_manager.py                71     28     22      7  55.9%
app\middleware\user_provisioner.py               18      7      4      1  63.6%
app\services\audit_service_postgres.py          191    149     26      0  19.4%
app\services\base.py                            171     50     32      9  69.0%
app\services\cache_cleanup_service.py            52     31     10      0  37.1%
app\services\compliance_checking_service.py     202    202     74      0   0.0%
app\services\config_validator.py                 17     10      6      0  30.4%
app\services\configuration_service.py            12      4      2      0  57.1%
app\services\encryption_service.py               92     50     20      4  41.1%
app\services\genesys_cache_db.py                266    225     78      0  11.9%
app\services\genesys_service.py                 309    203    116     12  28.7%
app\services\graph_service.py                   221    191     72      0  10.2%
app\services\job_role_mapping_service.py        167    137     58      0  13.3%
app\services\job_role_warehouse_service.py      233    193     46      1  14.7%
app\services\ldap_service.py                    289    116     88     21  54.6%
app\services\refresh_employee_profiles.py       358    292     80      4  16.4%
app\services\result_merger.py                   202     98    100     22  47.7%
app\services\search_enhancer.py                 112     76     34      4  31.5%
app\services\search_orchestrator.py             165     32     36     11  78.6%
app\services\simple_config.py                   166     89     38      5  42.2%
app\services\token_refresh_service.py           111     87     42      0  17.0%
```

**Aggregate:**
- `app/middleware`: 416 stmts, 182 missed → **56.2%** line-only
- `app/services`: 3336 stmts, 2235 missed → **33.0%** line-only
- **Combined gate metric (line+branch):** **32.0%** vs. required 60% — **FAIL**

---

## D-12 Hot-Path File Coverage

D-12 deliberately narrowed seed-test scope to the 3 highest-value service files. These were delivered as scoped:

| File | Stmts | Coverage | Verdict |
|------|------:|---------:|---------|
| `app/services/search_orchestrator.py` | 165 | **78.6%** | Above 60% — exceeds D-12 expectation. |
| `app/services/ldap_service.py` | 289 | **54.6%** | Below 60% — boundary tests only; entry-processing helpers (lines 295-354, 374-460, 482-547, 601, 609-649) untested. |
| `app/services/genesys_service.py` | 309 | **28.7%** | Below 60% — `search_user` + token round-trip + `test_connection` covered; bulk Genesys cache/refresh internals untested. |

D-12's scope (3 hot-path files seed-tested) is met. The 60% gate on the **whole** services package (D-11) is not, and that is the gap.

---

## Anti-Patterns / Findings

| File | Finding | Severity | Impact |
|------|---------|----------|--------|
| `tests/conftest.py` | SAVEPOINT pattern (D-03) replaced with TRUNCATE-on-teardown for `db_session` | Info | Documented in `deferred-items.md` (Plan 02-03 auto-fix #2). Achieves the same isolation goal; deviation from D-03 should be ratified by override or amended decision record. |
| `app/blueprints/search/__init__.py:1065` | `_render_unified_profile` AttributeError on missing source data | Warning | Pre-existing production bug surfaced by Plan 03 search-flow tests (4 strict-xfails). Out of Phase 2 scope (blueprint hardening deferred per 02-CONTEXT.md). Strict-xfail will convert to fail-on-pass when fixed, forcing re-evaluation. |
| `app/services/simple_config.py:102,159` | `config_get` reads `simple_config` table; `config_set` writes `configuration` table | Warning | Pre-existing production bug. Workaround in tests (pre-populate `service._config_cache`). |
| `app/models/api_token.py:117` | `if not token.is_expired:` — `is_expired` is a method, not a property; always truthy | Warning | Pre-existing production bug. Cached-token path always misses; production masks via fetch-new-token fallback. Workaround in tests (`mocker.patch.object(ApiToken, "get_token", ...)`). |
| Suite-wide | `--cov-fail-under=60` blocks ALL pushes today, even no-test-change pushes | **Blocker** | Until coverage gap closes, every push requires `--no-verify`. The gate works as designed; the codebase doesn't satisfy it. This is the primary Phase 2 gap. |
| Test-warnings | 4 deprecation warnings (pyasn1 tagMap/typeMap, flask-limiter in-memory storage, simple_config `datetime.utcnow()`) | Info | Pre-existing, none Phase-2 introduced. |

---

## Behavioral Spot-Checks

| Behavior | How Verified | Result | Status |
|----------|--------------|--------|--------|
| Pre-push hook exists and is executable | File at `.githooks/pre-push`, mode 100755, contains `make test` | Confirmed | PASS |
| Makefile target `test` calls pytest | `Makefile:test:` body is `pytest -x` | Confirmed | PASS |
| Coverage gate is configured at 60% | `pyproject.toml [tool.pytest.ini_options]` `addopts` includes `--cov-fail-under=60` | Confirmed | PASS |
| TESTING flag gates background threads | `app/__init__.py` lines 141, 163, 184, 193, 201 all check `os.environ.get("TESTING") or app.config.get("TESTING")` before `.start()` calls | Confirmed | PASS |
| Production requirements free of dev tools | `grep pytest\|factory-boy\|testcontainers\|^ruff\|^mypy requirements.txt` returns no matches | Confirmed | PASS |
| Suite runs without external API calls | 18.71s wall time across 40 tests (incl. 8 integration), only network is to localhost testcontainer | Confirmed (Wave-4 run report) | PASS |
| Coverage gate currently FAILS at 60% threshold | `FAIL Required test coverage of 60% not reached. Total coverage: 31.99%` from Wave-4 run | Confirmed | FAIL (this IS the gap) |

---

## Deferred Items (Step 9b filter)

ROADMAP Phase 3 success criteria were inspected for coverage of the 5 zero/low-tested service files (refresh_employee_profiles, genesys_cache_db, compliance_checking_service, job_role_warehouse_service, job_role_mapping_service). **None of Phase 3's SCs (containerization, gunicorn, Traefik, env-var config, structured logs, portal registration) address coverage of these files.** Phase 3 explicitly *depends on* Phase 2's tests existing — it will not add the missing tests for us.

Therefore the coverage gap is **NOT deferrable** to a later milestone phase. It must be closed by either:
  - (a) A new Wave-5 / 02-05 plan that adds boundary tests for the 5 files (preferred), OR
  - (b) An explicit REQUIREMENTS.md amendment narrowing TEST-04's scope (contract change — requires user decision and override entry).

The 3 production bugs (search blueprint AttributeError, simple_config table mismatch, ApiToken.is_expired truthy-bug) are correctly handled via strict-xfail markers — they will flip to XPASS when fixed, forcing re-evaluation. They are NOT Phase 2 gaps; they are pre-existing production debt that Phase 2's suite usefully surfaced.

---

## Gaps Summary

**The single Phase 2 gap is coverage: 32.0% combined vs. 60% required.**

Everything else Phase 2 promised is in place and provably functional:
- pytest infrastructure (D-01, D-02, D-03 with TRUNCATE-deviation, D-04, D-05, D-06, D-07, D-08)
- Container-level fakes for all 3 external APIs
- Targeted unit tests for the 3 D-12 hot-path service files
- Integration tests for auth pipeline (6 tests) and search flow (9 tests, 4 against pre-existing bugs)
- Pre-push hook with documented installer and `--no-verify` escape
- Makefile + pyproject.toml + requirements split + README docs
- 3 production bugs cleanly captured as strict-xfails (suite acts as a regression gate today)

The gap is **scope mismatch between D-11 (60% gate on all of services + middleware) and D-12 (seed tests for only 3 hot-path files)**. The plan implicitly assumed the 3 hot-path tests would lift overall coverage past 60%; in practice, with 5 sizeable un-tested service files (~1049 missed statements) those 3 files cannot move the aggregate that far.

**Recommended remediation path** (closure plan should pick one):
1. **02-05-coverage-closure** — Add ~10-15 boundary-style tests targeting the 5 zero/low-coverage service files. Preserves the 60% gate as the contract.
2. **REQUIREMENTS.md amendment** — Narrow TEST-04 to "60% on app/middleware/ + the D-12 hot-path service files" and update pyproject.toml `[tool.coverage.run] source` accordingly. Requires user sign-off and a verification override entry; preserves green CI but reduces the gate's value.

The verifier recommends path (1).

---

_Verified: 2026-04-25 (canonical, supersedes Wave-4 draft)_
_Verifier: Claude (gsd-verifier, Opus 4.7 1M)_

---

## Gap Closure (Plan 02-05) — appended 2026-04-25 — PARTIAL

**Plan:** `02-05-coverage-closure-PLAN.md`
**Closes gap:** ROADMAP SC #2 / TEST-04 — services + middleware coverage ≥60%
**Status:** **PARTIAL — per-file targets met; aggregate gate NOT yet reached (41.31% vs 60% required).**

### Summary

Tasks 1-4 of the plan were executed: 5 new test modules + 1 new factory landed, lifting per-file coverage on each of the 5 targeted services well above their per-file targets. However, the aggregate `--cov-fail-under=60` gate still fails at 41.31%, because un-scoped service files (graph_service.py 10.2%, result_merger.py 9.6%, search_enhancer.py 0.0%, token_refresh_service.py 17.0%, audit_service_postgres.py 16.6%, genesys_service.py 29.4%) collectively retain ~1000+ missed statements. The plan explicitly flagged this risk and named those files as "NOT scoped to this plan."

### Per-File Coverage Lift (Plan 02-05 targets)

| File | Before (Wave-4) | After (Plan 02-05) | Plan Target | Met? |
|------|----------------:|-------------------:|------------:|:----:|
| compliance_checking_service.py | 0.0% | **68.8%** | ≥50% | YES |
| genesys_cache_db.py | 11.9% | **65.4%** | ≥45% | YES |
| job_role_mapping_service.py | 13.3% | **66.7%** | ≥50% | YES |
| job_role_warehouse_service.py | 14.7% | **56.6%** | ≥45% | YES |
| refresh_employee_profiles.py | 16.4% | **36.5%** | ≥40% | NO (3.5pp short) |

### Aggregate Gate Status

- `pytest tests/` exit code: **non-zero** (gate fails + 5 integration test failures)
- `--cov-fail-under=60` in pyproject.toml: **STILL FAILS** (combined coverage 41.31% vs 60%)
- pyproject.toml `--cov-fail-under` value: **60** (unchanged from Plan 02-04 — D-11 contract preserved)

### Tests Added (Plan 02-05)

| File | Tests | Passing | xfail-strict |
|------|------:|--------:|-------------:|
| test_job_role_mapping_service.py | 12 | 12 | 0 |
| test_compliance_checking_service.py | 23 | 23 | 0 |
| test_genesys_cache_db.py | 11 | 11 | 0 |
| test_refresh_employee_profiles.py | 16 | 9 | 7 |
| test_job_role_warehouse_service.py | 19 | 19 | 0 |
| **Total Plan-02-05 tests** | **81** | **74** | **7** |

### Integration Test Failures (out-of-scope but blocks `pytest tests/` exit 0)

5 integration tests fail with HTTP 302 redirects instead of 200:
- `test_auth_pipeline.py::test_audit_log_or_user_row_appears_after_admin_visit`
- `test_search_flow.py::test_search_returns_merged_result_from_all_three_sources`
- `test_search_flow.py::test_search_no_results_returns_empty_state`
- `test_search_flow.py::test_search_multiple_ldap_results_renders`
- `test_search_flow.py::test_search_empty_term_returns_prompt`

**Root cause:** Phase 9 (SandCastle/OIDC) work landed on this branch in parallel — the auth pipeline migration from header-based auth to Authlib OIDC changed the test client's auth bypass path. These failures are Phase 9 regressions, not Plan 02-05 scope.

### Verification Status (re-run)

| ROADMAP SC | Wave-4 Status | Plan-02-05 Status |
|------------|---------------|-------------------|
| #2 services + middleware ≥60% | FAIL (32.0%) | **STILL FAIL (41.31%)** |

### Remaining Work to Close the Gate

A follow-up plan (suggested: 02-06 or roll into 03) needs to close the remaining 18.7pp gap by adding boundary tests for at least these out-of-scope files:
- `result_merger.py` (9.6% → target ≥50%, ~150 stmts)
- `search_enhancer.py` (0.0% → target ≥40%, ~95 stmts)
- `graph_service.py` (10.2% → target ≥40%, ~140 stmts)
- `token_refresh_service.py` (17.0% → target ≥40%, ~80 stmts)
- `audit_service_postgres.py` (16.6% → target ≥40%, ~100 stmts)

Closing 50% of each would lift aggregate coverage to ~60-62%.

### Phase 2 Verification Status

Phase 2 verification status remains `gaps_found`. The single gap (60% aggregate gate) is partially closed: 32.0% → 41.31% (+9.3pp). It will require additional test work in a follow-up plan to fully close.

_Plan-02-05 partial verification: 2026-04-25_
