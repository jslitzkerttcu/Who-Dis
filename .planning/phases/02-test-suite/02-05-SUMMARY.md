---
phase: 02-test-suite
plan: 05
status: partial
date: 2026-04-25
---

# Plan 02-05: Coverage Closure — SUMMARY

**Status: PARTIAL.** Per-file targets met for 4 of 5 services; aggregate `--cov-fail-under=60` gate still fails (41.31% vs 60%). Follow-up plan needed to close the remaining gap.

## What Shipped

**1 new factory + 5 new test modules:**

- `tests/factories/job_role_mapping.py` — `JobRoleMappingFactory` (factory_boy) for compliance/mapping tests
- `tests/factories/__init__.py` — package marker
- `tests/unit/services/test_job_role_mapping_service.py` (12 tests, all passing)
- `tests/unit/services/test_compliance_checking_service.py` (23 tests, all passing — pure helpers + DB-driven)
- `tests/unit/services/test_genesys_cache_db.py` (11 tests, all passing — `requests` mocked at module boundary)
- `tests/unit/services/test_refresh_employee_profiles.py` (9 passing + 7 xfail-strict — `pyodbc`/`httpx` mocked)
- `tests/unit/services/test_job_role_warehouse_service.py` (19 tests, all passing — `pyodbc` mocked)

**Total: 81 tests added (74 passing + 7 xfail-strict). No production code modified.**

## Per-File Coverage Delta

| File | Before | After | Delta | Target | Met? |
|---|--:|--:|--:|--:|:-:|
| compliance_checking_service.py | 0.0% | 68.8% | +68.8pp | ≥50% | YES |
| genesys_cache_db.py | 11.9% | 65.4% | +53.5pp | ≥45% | YES |
| job_role_mapping_service.py | 13.3% | 66.7% | +53.4pp | ≥50% | YES |
| job_role_warehouse_service.py | 14.7% | 56.6% | +41.9pp | ≥45% | YES |
| refresh_employee_profiles.py | 16.4% | 36.5% | +20.1pp | ≥40% | NO (3.5pp short) |

## Aggregate Gate (NOT met)

- Combined services+middleware coverage: **41.31%** (was 32.0%; required: 60%)
- `--cov-fail-under=60` in pyproject.toml: **STILL FAILS** (gate value preserved per D-11 — not lowered)
- `pytest tests/` exits non-zero (gate fail + 5 integration test failures from collateral Phase 9 OIDC migration)

## xfail-strict Markers Added

7 markers in `test_refresh_employee_profiles.py` for tests that surface known production bugs documented in `deferred-items.md`:
- `EmployeeProfilesRefreshService.execute_keystone_query` import-time failure paths when `pyodbc` is None
- Async `refresh_all_profiles` orchestrator bypass tests (heavyweight; deferred per plan)

These will flip to XPASS if the underlying production code is fixed, forcing re-evaluation.

## Why the Aggregate Gate Did Not Close

The plan explicitly named 5 service files as targets and 5 service files as out-of-scope. Closing the 5 in-scope files added ~9.3pp to aggregate coverage (32% → 41.31%). The remaining ~19pp lives in:

| File | Coverage | Missed Stmts |
|---|--:|--:|
| graph_service.py | 10.2% | 191 |
| result_merger.py | 9.6% | 173 |
| search_enhancer.py | 0.0% | 112 |
| token_refresh_service.py | 17.0% | 92 |
| audit_service_postgres.py | 16.6% | 155 |
| genesys_service.py | 29.4% | 200 |

The plan flagged this risk in Task 5: *"if the aggregate still doesn't reach 60%, the bottleneck is most likely audit_service_postgres.py or graph_service.py — these are NOT scoped to this plan."*

## What This Means for the Developer

- ❌ `git push` STILL requires `--no-verify` from a clean clone — the pre-push hook still fails
- ❌ `make test` still exits non-zero (gate fail)
- ✅ The 5 cold-path services now have boundary regression protection ahead of Phase 3 containerization
- ✅ Per-file coverage on the targeted files is solid (56-69%)
- ✅ `JobRoleMappingFactory` available for any future compliance-related tests

## Recommended Next Step

A new plan **02-06-coverage-closure-round-2** (or fold into Phase 3) that adds boundary tests for at least:
- `result_merger.py` (highest priority — search-flow critical path)
- `search_enhancer.py` (currently 0% — search-flow critical path)
- `graph_service.py` (real implementation never runs; only FakeGraphService does)
- `token_refresh_service.py` (background job)

Targeting ~50% on each closes ~250 statements which would lift aggregate from 41.31% to ~60-62%.

## Notes on Branch Context

Plan 02-05 work landed on `feat/sandcastle-onboarding-phase-9` alongside Phase 9 OIDC/SandCastle commits. The 5 integration test failures (302 redirects instead of 200) are Phase 9 collateral, not Plan 02-05 scope — the auth pipeline migration from header-based to Authlib OIDC changed the test client's auth bypass path. Those tests will need fixture updates as part of the Phase 9 PR (#25) review.

## Files Touched

- New: `tests/factories/__init__.py`, `tests/factories/job_role_mapping.py`
- New: `tests/unit/services/test_compliance_checking_service.py`
- New: `tests/unit/services/test_genesys_cache_db.py`
- New: `tests/unit/services/test_job_role_mapping_service.py`
- New: `tests/unit/services/test_job_role_warehouse_service.py`
- New: `tests/unit/services/test_refresh_employee_profiles.py`
- Edited: `tests/conftest.py` (config_get shims for tests — preserves test-time access to encrypted-config patterns)
- Appended: `.planning/phases/02-test-suite/02-VERIFICATION.md` (Gap Closure section, marked PARTIAL)

No production code in `app/`, `requirements*.txt`, `Makefile`, `.githooks/` modified by this plan.

---
_Plan executed: 2026-04-25 (partial — gate not yet passing). Executor: gsd-executor / Sonnet 4.6 (interrupted by usage limits). Completed by: Claude (Opus 4.7 1M)._
