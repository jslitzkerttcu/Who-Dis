---
phase: 08
slug: reporting
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-17
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `pytest tests/ -x -q --timeout=10` |
| **Full suite command** | `pytest tests/ -v --cov=app --cov-report=term-missing` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --timeout=10`
- **After every plan wave:** Run `pytest tests/ -v --cov=app --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-T1 | 01 | 1 | REPT-08 | — | N/A | unit | `python -c "from app.models.report_cache import ReportCache; assert hasattr(ReportCache, 'is_stale'); assert hasattr(ReportCache, 'store')"` | ❌ W0 | ⬜ pending |
| 08-01-T2 | 01 | 1 | REPT-01, REPT-03, REPT-05 | — | N/A | unit | `python -c "from app.services.graph_service import GraphService; assert hasattr(GraphService, 'get_all_users_with_licenses')"` | ❌ W0 | ⬜ pending |
| 08-01-T3 | 01 | 1 | REPT-01, REPT-02, REPT-03, REPT-04, REPT-06, REPT-07 | T-08-02 | admin_or_portal_required on job endpoints | unit | `python -c "from app.services.report_sync_service import ReportSyncService; from app.blueprints.admin.jobs import JOB_REGISTRY; assert 'report_license_sync' in [j['name'] for j in JOB_REGISTRY]"` | ❌ W0 | ⬜ pending |
| 08-02-T1 | 02 | 2 | REPT-01, REPT-02, REPT-03, REPT-04 | T-08-05, T-08-06 | _csv_safe on exports; _validate_date on date params | unit | `python -c "from app.blueprints.admin.reports import reports, export_license_csv, _csv_safe; assert _csv_safe('=CMD()') == \"'=CMD()'\""` | ❌ W0 | ⬜ pending |
| 08-02-T2 | 02 | 2 | REPT-01, REPT-08 | T-08-08 | Jinja2 autoescaping | template | `python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('app/templates')); [env.get_template(t) for t in ['admin/reports.html','admin/partials/_report_licenses.html','admin/partials/_report_security.html','admin/partials/_report_stale_badge.html']]"` | ❌ W0 | ⬜ pending |
| 08-03-T1 | 03 | 3 | REPT-05, REPT-06, REPT-07 | T-08-11 | _csv_safe on Genesys export | unit | `python -c "from app.blueprints.admin.reports import api_genesys_tab, api_history_tab, export_genesys_csv; assert callable(api_genesys_tab)"` | ❌ W0 | ⬜ pending |
| 08-03-T2 | 03 | 3 | REPT-05, REPT-07 | T-08-10 | Jinja2 autoescaping on Genesys data | template | `python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('app/templates')); [env.get_template(t) for t in ['admin/partials/_report_genesys.html','admin/partials/_report_history.html']]"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_report_cache.py` — stubs for REPT-08 (model, is_stale, store, get_cached)
- [ ] `tests/test_report_sync_service.py` — stubs for REPT-01..04 (license sync, security sync, hybrid sign-in query)
- [ ] `tests/test_report_routes.py` — stubs for REPT-05..07 (report tab routes, CSV exports, history tab)
- [ ] Mock fixtures for Graph bulk API responses (userRegistrationDetails, users with licenses, signIn logs)

*Existing test infrastructure (pytest, conftest, fixtures) covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Report dashboard renders correctly with real data | REPT-01..04 | Visual layout verification | Navigate to /admin/reports, verify tabs render, data displays |
| Stale cache indicator visible | REPT-08 | Visual UI element | Let cache expire, verify indicator appears |
| Genesys presence shows live data | REPT-05 | Requires active Genesys agents | Open Contact Center tab, verify presence dots and routing status |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
