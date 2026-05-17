---
phase: 07
slug: compliance-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-16
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q --timeout=10` |
| **Full suite command** | `pytest tests/ --timeout=30` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --timeout=10`
- **After every plan wave:** Run `pytest tests/ --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | COMP-01 | — | Job endpoint requires admin role or portal M2M token | integration | `pytest tests/test_job_manager.py -k progress` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | COMP-04 | — | Warehouse errors display human-readable category, not raw trace | unit | `pytest tests/test_warehouse_errors.py` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 2 | COMP-02 | — | Client-side sort produces correct severity ordering | manual | Browser test — sort columns | N/A | ⬜ pending |
| 07-02-02 | 02 | 2 | COMP-03 | — | CSV export contains all required columns with metadata header | unit | `pytest tests/test_csv_export.py` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 2 | COMP-05 | — | Sync status shows last_success_at timestamp and re-sync button | integration | `pytest tests/test_sync_status.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_job_manager.py` — stubs for COMP-01 job progress tracking
- [ ] `tests/test_warehouse_errors.py` — stubs for COMP-04 error categorization
- [ ] `tests/test_csv_export.py` — stubs for COMP-03 CSV output validation
- [ ] `tests/test_sync_status.py` — stubs for COMP-05 sync metadata display
- [ ] `tests/conftest.py` — shared fixtures (db session, test client, admin user)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HTMX progress bar polls and auto-replaces | COMP-01 | Requires browser rendering + HTMX runtime | Run compliance check in browser, observe polling every 2s, verify bar updates and table swaps in |
| Column sort toggles ascending/descending | COMP-02 | Client-side JS sort requires DOM interaction | Click each column header, verify sort direction toggles and severity ranking is correct |
| Re-sync button disables during active sync | COMP-05 | Timing-dependent UI state | Click re-sync, verify button grays out and re-enables on completion |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
