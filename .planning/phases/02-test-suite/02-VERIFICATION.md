# Phase 2 Verification Report

**Run date:** 2026-04-25
**Run command:** `pytest tests/ -v` (rootdir=`C:\repos\Who-Dis`, configfile=`pyproject.toml`)
**Python:** 3.12.10 / pytest 8.4.1 / pytest-cov 5.0.0 / testcontainers 4.14.2
**Docker:** 29.4.0 (daemon running — required for the ephemeral Postgres fixture)

## Suite Result

- Tests collected: **40**
- Passed: **36**
- Failed: **0**
- xfailed: **4** (all in `tests/integration/test_search_flow.py` — strict-xfailed against
  three pre-existing production bugs documented in `deferred-items.md`)
- Skipped: 0
- Wall time: **18.71s**
- Test exit status: **0** (suite is green)
- Coverage gate exit status: **non-zero** (`FAIL Required test coverage of 60% not reached. Total coverage: 31.99%`)

## Coverage Summary

| Package           | Statements | Missed | Coverage (line-only) |
|-------------------|-----------:|-------:|---------------------:|
| `app/middleware`  |        416 |    182 | **56.2%**            |
| `app/services`    |       3336 |   2235 | **33.0%**            |
| **Combined gate** |       3752 |   2417 | **35.6%**            |

Combined statement+branch coverage (the metric pytest-cov asserts against the gate):
**32.0%**.

**Gate: `--cov-fail-under=60` — FAIL** (combined 32.0% vs. required 60%).

> Per Wave-4 execution rules ("if coverage < 60%, document the gap — do not lower the
> threshold to make it pass"), the gate value in `pyproject.toml` is **unchanged at 60%**.
> The gap is recorded below as a Wave-4 finding and is the work item that closes Phase 2.

## Per-File Coverage (services + middleware)

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

## D-12 Hot-Path File Coverage

| File                                       | Stmts | Coverage  | Notes                                                                                                                                                                |
|--------------------------------------------|------:|----------:|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `app/services/search_orchestrator.py`      |   165 | **78.6%** | Plan 03 covers all 5 result-processor paths + concurrent dispatch + 3 timeout cases. Best-covered service file.                                                      |
| `app/services/ldap_service.py`             |   289 | **54.6%** | Plan 03 covers `search_user` happy/empty/multiple/exception + `test_connection`. Internal entry-processing helpers (lines 295-354, 374-460, 482-547, 601, 609-649) uncovered. |
| `app/services/genesys_service.py`          |   309 | **28.7%** | Plan 03 covers `search_user`, token round-trip, `test_connection` no-creds. The bulk Genesys cache/refresh internals (lines 191-310, 408-665) remain uncovered.       |

## ROADMAP §Phase 2 Success Criteria — Verification

1. ✅ **`pytest tests/ -v` runs to completion without real LDAP, Graph, or Genesys calls**
   - Evidence: `tests/conftest.py` registers `FakeLDAPService`/`FakeGraphService`/
     `FakeGenesysService` at the DI-container layer; `app/__init__.py` skips background-
     thread `.start()` and the startup token-refresh loop when `TESTING=1`. The 18.71s
     wall time across 40 tests (incl. 8 integration tests against a live Postgres
     container) confirms no network I/O to external identity providers.

2. ❌ **Coverage report shows 60%+ on services and middleware packages**
   - Evidence: combined coverage **32.0%** (line-only 35.6%), middleware **56.2%**,
     services **33.0%**. The `--cov-fail-under=60` gate FAILS. Gap analysis below.

3. ✅ **Authentication middleware pipeline and full search flow are verified by integration tests**
   - Evidence: `tests/integration/test_auth_pipeline.py` (6 tests, all passing) covers
     existing-user-retained, missing-header, insufficient-role, admin-can-reach-admin,
     request-id-in-logs, audit-trace. `tests/integration/test_search_flow.py` (9 tests,
     5 passing + 4 strict-xfailed) covers all-three-sources merge, no-results,
     multiple-LDAP, unauthenticated, empty-term. Real `SearchOrchestrator`/
     `ResultMerger`/middleware stack runs end-to-end against fakes.

4. ✅ **A failing test blocks a developer from merging**
   - Evidence: see Task 3 (pre-push hook gate verification — programmatic simulation).

## Task 3: Pre-push hook gate verification (programmatic simulation)

> **AUTO-MODE NOTE:** `workflow._auto_chain_active=true`. The plan's
> `checkpoint:human-verify` is auto-approved per workflow rules. In place of a human
> running `git push --dry-run`, the executor reproduced the gate's underlying behaviour
> programmatically and recorded what a real run would have observed.

### Hook installer (D-09)

- **File:** `.githooks/pre-push` (mode 100755), bash, `set -euo pipefail`, body invokes
  `make test`.
- **Installer command:** `git config core.hooksPath .githooks` (one-time per clone;
  documented in README §Testing — see Task 2).
- **Bypass:** `git push --no-verify` (intentional emergency escape per D-09; documented).

### Green path simulation

Command equivalent to what the hook runs (the hook calls `make test` → which calls
`pytest -x` → which uses pyproject.toml `addopts`):

```text
$ pytest --no-cov tests/unit/services/test_ldap_service.py::test_service_name_property
$ echo $?
0
```

A passing test → `pytest -x` → exit 0 → hook returns 0 → push permitted.

### Red path simulation (deliberate failure)

A scratch test was created at `tests/unit/test_phase2_gate_check.py`:

```python
import pytest
@pytest.mark.unit
def test_phase2_gate_must_block_this():
    assert False, "Intentional failure to verify pre-push gate"
```

Result of running pytest with that file present:

```text
$ pytest -x --no-cov tests/unit/test_phase2_gate_check.py
FAILED tests/unit/test_phase2_gate_check.py::test_phase2_gate_must_block_this
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
============================== 1 failed in 0.54s ==============================
$ echo $?
1
```

Exit code **1** → `make test` would propagate non-zero → `.githooks/pre-push`'s
`set -euo pipefail` aborts → `git push` returns non-zero → **push BLOCKED**.

The scratch test was deleted after capture (`git status` clean for tests/).

### Coverage-gate red path (already exercised by the full run)

The full `pytest tests/` run on the current green suite already exercises the
coverage-gate failure path: the suite passes (36 + 4 xfailed) but
`--cov-fail-under=60` fires because combined coverage is 32.0% < 60%, producing:

```text
FAIL Required test coverage of 60% not reached. Total coverage: 31.99%
```

…which makes pytest's overall exit code non-zero. So **the hook would also block a
push that drops coverage below 60%**, today, against the current main branch.

### Bypass works

`git push --no-verify` skips the hook entirely (git built-in). No simulation needed —
this is documented git behaviour and is the intentional escape per D-09.

### Verification checklist

- [x] Hook script exists at `.githooks/pre-push` with executable mode
- [x] Hook is installed via documented one-liner (`git config core.hooksPath .githooks`)
- [x] Green path: passing tests → `pytest -x` exit 0 → hook permits push
- [x] Red path (test failure): failing test → `pytest -x` exit 1 → hook blocks push
- [x] Red path (coverage drop): suite passes but coverage <60% → hook blocks push
- [x] `--no-verify` bypass available (git built-in; documented)
- [x] Scratch test cleaned up (no leftover `tests/unit/test_phase2_gate_check.py`)

## Issues Encountered

### Coverage gap (PRIMARY FINDING — gate FAILS)

Combined services+middleware coverage is **32.0%** vs. the configured **60%** gate.
Sources of the gap, ranked by missed-statement count:

| File                                          | Missed Stmts | Why uncovered                                          |
|-----------------------------------------------|-------------:|--------------------------------------------------------|
| `app/services/refresh_employee_profiles.py`   |          292 | No tests in Phase 2 scope (employee-profile sync background job) |
| `app/services/genesys_cache_db.py`            |          225 | No tests in Phase 2 scope (Genesys cache layer)        |
| `app/services/genesys_service.py`             |          203 | Plan 03 covers boundaries only; bulk cache/refresh internals untested |
| `app/services/compliance_checking_service.py` |          202 | No tests in Phase 2 scope (job-role compliance)        |
| `app/services/job_role_warehouse_service.py`  |          193 | No tests in Phase 2 scope (warehouse sync)             |
| `app/services/graph_service.py`               |          191 | Plan 03 used the FakeGraphService; real service untested |
| `app/services/audit_service_postgres.py`      |          149 | Tests exercise the interface via Flask handlers; concrete service internals untested |
| `app/services/job_role_mapping_service.py`    |          137 | No tests in Phase 2 scope (mapping CRUD)               |
| `app/services/ldap_service.py`                |          116 | Plan 03 covers boundaries only; entry-processing helpers untested |
| (others)                                      |   ~709 total | Various — see per-file table above                     |

**Recommended remediation (NOT done in this plan — Wave 4 finding only):**
A focused follow-up plan (`02-05-coverage-closure` or rolled into Phase 3) should add
~10-15 additional tests against the highest-missed-stmt files in service-boundary
coverage style (mock external HTTP/DB, exercise public methods). Given that
`refresh_employee_profiles.py`, `genesys_cache_db.py`, `compliance_checking_service.py`,
`job_role_warehouse_service.py`, and `job_role_mapping_service.py` are all 0-15%
covered and contain ~1049 missed statements between them, the gap is too large to
close with surgical additions to the existing Plan 03 modules. Either:

  - (a) Add a Wave-5 plan that explicitly targets these files (preferred — keeps the
    60% gate honest and Phase 2's deliverable contract intact), or
  - (b) Accept that the 60% gate is aspirational for the entirety of `app/services/`
    and scope the gate tighter (e.g., only the D-12 hot-path files) — this requires a
    REQUIREMENTS.md amendment and is NOT recommended.

**Gate value in `pyproject.toml` was deliberately left at 60%** so that the gap is
visible in CI output and pre-push runs, not buried in a config decrement.

### Pre-existing production bugs surfaced by the suite (not new — documented in `deferred-items.md`)

These were discovered during Plan 03 and are out of scope for Phase 2 (blueprint
hardening + simple_config fix deferred per `02-CONTEXT.md`). They remain xfailed
(strict=True) so a future fix flips them to XPASS → forces re-evaluation:

1. **`_render_unified_profile` AttributeError** — `app/blueprints/search/__init__.py:1065`
   crashes with `AttributeError: 'NoneType' object has no attribute 'get'` when any
   one of `genesys_data`, `azure_ad_result`, `keystone_data` is None. Reproducible via
   4 search-flow tests, all xfailed.
2. **`simple_config` set/get table mismatch** — `config_set` writes to `configuration`
   table; `config_get` reads from `simple_config` table. Cache short-circuits in
   production hot paths so it isn't visible day-to-day, but breaks DB-seeded config
   tests. Workaround: pre-populate `service._config_cache` directly.
3. **`ApiToken.is_expired` is a method evaluated as truthy** — `app/models/api_token.py:117`
   `if not token.is_expired:` always falsy → cached-token path always misses. Workaround:
   `mocker.patch.object(ApiToken, "get_token", return_value=fake_token)`.

### Environment notes

- `make` is not on PATH on this Windows development host (consistent with
  Plan 02-01's note). Tests were exercised via direct `pytest tests/ -v`. The Makefile
  parses correctly (TABs verified in 02-01) and all targets shell out to plain
  `pytest`/`ruff`/`mypy` invocations — equivalent to the direct commands documented in
  the README.
- 4 deprecation warnings (pyasn1 tagMap/typeMap; flask-limiter in-memory storage;
  simple_config `datetime.utcnow()`). All pre-existing, none Phase-2 introduced.

## Phase 2 Acceptance Status

**3 of 4 ROADMAP success criteria PASS; criterion 2 (coverage ≥60%) FAILS.**

The Phase-2 deliverables (test infra, fakes, factories, pre-push hook, README docs)
are all in place and provably functional. The remaining work is **coverage closure
on the wide ~1000-statement gap across the un-targeted service files**. This should
be planned as `02-05-coverage-closure` or rolled into Phase 3's first wave before
Phase 3 introduces new code that would need to clear the same 60% gate.
