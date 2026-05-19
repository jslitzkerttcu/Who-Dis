---
phase: 11
slug: workflow-automation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-17
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/ -x -q --timeout=10` |
| **Full suite command** | `python -m pytest tests/ -v --timeout=30` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q --timeout=10`
- **After every plan wave:** Run `python -m pytest tests/ -v --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | WKFL-01, WKFL-02, WKFL-03 | — | N/A | unit | `python -m pytest tests/test_workflow_service.py -v` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | WKFL-01, WKFL-02 | — | N/A | unit | `python -m pytest tests/test_workflow_models.py -v` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 2 | WKFL-01, WKFL-02, WKFL-03 | — | Admin role required | integration | `python -m pytest tests/test_workflow_routes.py -v` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 2 | WKFL-04 | — | Admin role required | integration | `python -m pytest tests/test_workflow_dashboard.py -v` | ❌ W0 | ⬜ pending |
| 11-03-01 | 03 | 2 | WKFL-04 | — | N/A | manual | Browser verification | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_workflow_models.py` — stubs for Workflow, WorkflowItem, StandardOffboardingItem models
- [ ] `tests/test_workflow_service.py` — stubs for WorkflowService methods
- [ ] `tests/test_workflow_routes.py` — stubs for workflow blueprint routes

*Existing test infrastructure (conftest.py, fixtures, fakes) covers shared requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard shows active workflows with progress bars | WKFL-04 | Visual rendering verification | Navigate to /admin/workflows, verify KPI cards and progress bars render |
| Overdue items highlighted with red border | WKFL-04 | Visual styling check | Create workflow with past-due items, verify red border-l-4 styling |
| Employee typeahead search | WKFL-01 | HTMX interaction | Type employee name in create form, verify dropdown results |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
