# Roadmap: WhoDis v3.0

**Milestone:** WhoDis v3.0 — IT Operations Platform
**Defined:** 2026-04-24
**Granularity:** Standard (5-8 phases)
**Requirements:** 52 v1 requirements across 11 categories

## Phases

- [ ] **Phase 1: Foundation** - Clean up tech debt, harden security, add operational primitives
- [ ] **Phase 2: Test Suite** - Establish automated testing infrastructure before write operations
- [ ] **Phase 3: Enriched Profiles & Search Export** - Surface full Graph/Genesys data on profile cards with export
- [ ] **Phase 4: Compliance Polish** - Bulk checks with progress, export, and warehouse sync visibility
- [ ] **Phase 5: Reporting** - License, security posture, and Genesys reports with scheduling
- [ ] **Phase 6: Write Operations** - AD account actions and license management from the UI
- [ ] **Phase 7: REST API** - Token-authenticated read-only API with rate limiting and docs
- [ ] **Phase 8: Workflow Automation** - Onboarding/offboarding checklists with completion tracking

## Phase Details

### Phase 1: Foundation
**Goal**: The codebase has a single clean initialization path, deprecated code is gone, security gaps are closed, and production operational primitives are in place
**Depends on**: Nothing (brownfield baseline)
**Requirements**: DEBT-01, DEBT-02, DEBT-03, DEBT-04, OPS-01, OPS-02, OPS-03, OPS-04, SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. Application starts with a single code path — `app/__init__.py` is the only factory, `app_factory.py` is deleted
  2. `GET /health` returns JSON with database status, usable by monitoring tools without authentication
  3. Every log line carries a request ID that can be used to trace a single user action end-to-end
  4. Application refuses to start with clear error messages when required configuration values are missing
  5. `.whodis_salt` is absent from git history and a CLI tool exists to safely rotate the encryption key
**Plans**: 9 plans
- [x] 01-01-debt-cleanup-PLAN.md — Consolidate app factory, remove DataWarehouseService, modernize asyncio (DEBT-01/02/04)
- [ ] 01-02-cache-cleanup-PLAN.md — Hourly SearchCache cleanup service + admin Run-now button (DEBT-03)
- [ ] 01-03-health-endpoints-PLAN.md — Unauthenticated /health and /health/live endpoints (OPS-01)
- [ ] 01-04-request-id-json-logging-PLAN.md — Request-ID middleware + JSON-structured logging (OPS-02)
- [ ] 01-05-config-validator-PLAN.md — Startup config validator that aborts boot on missing keys (OPS-03)
- [x] 01-06-pagination-PLAN.md — Reusable paginate helper + render_pagination macro wired into 3 admin tables (OPS-04)
- [ ] 01-07-salt-key-rotation-PLAN.md — Gitignore .whodis_salt + dual-key rotation script + runbook (SEC-01/02)
- [ ] 01-08-rate-limiting-PLAN.md — Flask-Limiter on /search and /api/search at 30/min per user (SEC-03)
- [ ] 01-09-auth-header-config-PLAN.md — Configurable auth header + dev bypass env var (SEC-04)
**UI hint**: yes

### Phase 2: Test Suite
**Goal**: Developers can run a full test suite that covers services and middleware, with mocked external APIs, preventing regressions before any write operations ship
**Depends on**: Phase 1
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. `pytest tests/ -v` runs to completion without real LDAP, Graph, or Genesys calls
  2. Coverage report shows 60%+ on services and middleware packages
  3. Authentication middleware pipeline and full search flow are verified by integration tests
  4. A failing test blocks a developer from merging (even without CI, the suite is runnable as a gate)
**Plans**: TBD

### Phase 3: Enriched Profiles & Search Export
**Goal**: Profile cards show the full picture of an employee — Graph licenses, MFA, last sign-in, Genesys queues and skills — without cluttering the default view, and users can export what they see
**Depends on**: Phase 1
**Requirements**: PROF-01, PROF-02, PROF-03, PROF-04, PROF-05, PROF-06, SRCH-01, SRCH-02
**Success Criteria** (what must be TRUE):
  1. Profile card shows department, manager, assigned licenses, MFA status, and last sign-in date from Graph
  2. Profile card shows Genesys queues, skills with proficiency levels, and current presence
  3. Extended data lives in collapsible sections that are closed by default — the default card is not cluttered
  4. Expensive fields (sign-in logs, licenses) load after the initial card render via HTMX, not blocking page paint
  5. User can copy a structured text summary to clipboard or download a CSV of all visible fields
**Plans**: TBD
**UI hint**: yes

### Phase 4: Compliance Polish
**Goal**: Admins running bulk compliance checks get real-time progress feedback, can export results, and can see when warehouse data was last synced — without encountering raw stack traces
**Depends on**: Phase 1
**Requirements**: COMP-01, COMP-02, COMP-03, COMP-04, COMP-05
**Success Criteria** (what must be TRUE):
  1. Bulk compliance check shows a live progress indicator (HTMX polling) — admin sees checks completing in real time
  2. Compliance results table is sortable by severity (critical first) without a page reload
  3. Admin can download compliance results as CSV with employee, job code, expected/actual roles, violation type, and severity columns
  4. Warehouse sync failures display a human-readable error message instead of a stack trace or blank screen
  5. Admin UI shows the timestamp of the last successful warehouse sync with a manual re-sync trigger button
**Plans**: TBD
**UI hint**: yes

### Phase 5: Reporting
**Goal**: Admins have a dedicated Reports section with license utilization, security posture, and Genesys agent status — all cached and schedulable
**Depends on**: Phase 1, Phase 3
**Requirements**: REPT-01, REPT-02, REPT-03, REPT-04, REPT-05, REPT-06, REPT-07, REPT-08
**Success Criteria** (what must be TRUE):
  1. Admin can view a license dashboard showing all M365 SKUs with assigned/available counts and unused license flags (no sign-in 30+ days)
  2. Admin can view MFA adoption rate as a percentage and a list of users without MFA configured
  3. Admin can view a failed sign-in table filterable by date range showing user, timestamp, failure reason, and IP
  4. Genesys section shows current presence, routing status, and queue memberships for Genesys-enabled users
  5. Admin can create, edit, and delete report schedules (daily/weekly/monthly) with a history view of past runs
  6. Report data is served from cache (4h licenses, 1h security, 5min Genesys) — a stale-cache indicator is visible
**Plans**: TBD
**UI hint**: yes

### Phase 6: Write Operations
**Goal**: Editors and admins can act on search results — unlocking accounts, resetting passwords, toggling AD account state, and managing licenses — with every action confirmed, audited, and reversible-by-audit-trail
**Depends on**: Phase 2, Phase 3
**Requirements**: WRIT-01, WRIT-02, WRIT-03, WRIT-04, WRIT-05, WRIT-06, WRIT-07, WRIT-08
**Success Criteria** (what must be TRUE):
  1. Editor can unlock a locked AD account, reset a password (shown once), or enable/disable an account directly from the search result view
  2. Every write action presents a confirmation modal requiring a typed reason before proceeding — the action does not fire without it
  3. Every write action (AD or license) creates an audit log entry with who, what, to whom, when, IP address, and the typed reason
  4. Admin can assign or remove an M365 license from the profile view with confirmation
  5. License swap (remove old SKU, assign new SKU) executes as an atomic operation — partial state is not left if one step fails
**Plans**: TBD
**UI hint**: yes

### Phase 7: REST API
**Goal**: External systems and automation can query WhoDis via a documented, rate-limited, token-authenticated API without touching the web UI
**Depends on**: Phase 2, Phase 3
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06
**Success Criteria** (what must be TRUE):
  1. Admin can create, view, and revoke API tokens from the admin UI using the existing ApiToken model
  2. External caller can search users via `GET /api/v1/search?q=` and retrieve a full profile via `GET /api/v1/user/{email}` using a bearer token
  3. Every API call is logged to the audit trail with the token ID, endpoint, and result status
  4. Rate limit is enforced per token — exceeding the limit returns 429 with a Retry-After header
  5. OpenAPI spec is accessible at `/api/v1/docs` without authentication
**Plans**: TBD

### Phase 8: Workflow Automation
**Goal**: Admins can generate onboarding and offboarding checklists from job role mappings, track each item's completion, and see active workflows on a dashboard
**Depends on**: Phase 4, Phase 6
**Requirements**: WKFL-01, WKFL-02, WKFL-03, WKFL-04
**Success Criteria** (what must be TRUE):
  1. Admin can select a job code and generate an onboarding checklist pre-populated from job role compliance mappings
  2. Admin can generate an offboarding checklist that mirrors and reverses all provisioning steps from onboarding
  3. Each checklist item records who completed it and when — the audit trail is queryable
  4. A workflow dashboard shows all active checklists with per-item progress and highlights overdue items
**Plans**: TBD
**UI hint**: yes

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/9 | In Progress|  |
| 2. Test Suite | 0/? | Not started | - |
| 3. Enriched Profiles & Search Export | 0/? | Not started | - |
| 4. Compliance Polish | 0/? | Not started | - |
| 5. Reporting | 0/? | Not started | - |
| 6. Write Operations | 0/? | Not started | - |
| 7. REST API | 0/? | Not started | - |
| 8. Workflow Automation | 0/? | Not started | - |

---
*Roadmap defined: 2026-04-24*
*Last updated: 2026-04-24 after initial creation*
