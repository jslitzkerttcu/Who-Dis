# Requirements: WhoDis v3.0

**Defined:** 2026-04-24
**Core Value:** IT staff can find everything about any employee and act on it from a single interface

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Testing

- [ ] **TEST-01**: Developer can run `pytest tests/ -v` and get passing unit tests for all service classes
- [ ] **TEST-02**: External APIs (LDAP, Graph, Genesys) are mocked at container level in test fixtures
- [ ] **TEST-03**: Integration tests verify authentication middleware pipeline and search flow end-to-end
- [ ] **TEST-04**: Coverage report generated with `pytest --cov=app` showing 60%+ on services and middleware

### Profile Data

- [ ] **PROF-01**: User can see department, manager, employee ID, assigned licenses, and last sign-in date from Graph API on profile card
- [ ] **PROF-02**: User can see MFA status and authentication methods from Graph API on profile card
- [ ] **PROF-03**: User can see Genesys queues, skills with proficiency levels, and current presence on profile card
- [ ] **PROF-04**: Extended data renders in collapsible sections that don't clutter the default view
- [ ] **PROF-05**: Expensive fields (sign-in activity, licenses) load asynchronously via HTMX after initial render
- [ ] **PROF-06**: Result merger handles missing fields gracefully without errors

### Search Export

- [ ] **SRCH-01**: User can click "Copy to Clipboard" to copy a structured text summary of displayed user data
- [ ] **SRCH-02**: User can click "Export CSV" to download all displayed fields with data source attribution

### Compliance

- [ ] **COMP-01**: Admin can see real-time progress during bulk compliance checks via HTMX polling
- [ ] **COMP-02**: Admin can sort violations by severity (critical > high > medium > low)
- [ ] **COMP-03**: Admin can export compliance results as CSV (employee, job code, expected/actual roles, violation type, severity)
- [ ] **COMP-04**: Warehouse sync failures display clear user-facing error messages instead of stack traces
- [ ] **COMP-05**: Admin UI shows when warehouse data was last synced with manual sync trigger

### Reporting

- [ ] **REPT-01**: Admin can view license utilization dashboard showing all M365 SKUs with assigned/available/consumed counts
- [ ] **REPT-02**: Dashboard highlights unused licenses (assigned but no sign-in in 30+ days) with utilization percentage per SKU
- [ ] **REPT-03**: Admin can view MFA adoption rate as percentage with list of non-MFA users
- [ ] **REPT-04**: Admin can view failed sign-in table with user, timestamp, failure reason, IP/location filterable by date range
- [ ] **REPT-05**: Contact center section shows current Genesys presence, routing status, and queue memberships for Genesys-enabled users
- [ ] **REPT-06**: Admin can create/edit/delete report schedules with daily/weekly/monthly presets
- [ ] **REPT-07**: Reports generate on schedule using background thread infrastructure with history view
- [ ] **REPT-08**: Report data cached with configurable TTL (4h licenses, 1h security, 5min Genesys status)

### Write Operations

- [ ] **WRIT-01**: Editor can unlock a locked AD account from the search result view
- [ ] **WRIT-02**: Editor can reset an AD password generating a temporary password displayed once
- [ ] **WRIT-03**: Editor can enable/disable AD accounts from the search result view
- [ ] **WRIT-04**: All write actions require confirmation modal with mandatory reason text
- [ ] **WRIT-05**: Every write action is logged to audit trail with full context (who, what, to whom, when, where, reason)
- [ ] **WRIT-06**: Admin can assign a license to a user from the profile view
- [ ] **WRIT-07**: Admin can remove a license with confirmation
- [ ] **WRIT-08**: License swap (remove old, assign new) supported as atomic operation

### API

- [ ] **API-01**: Admin can create and manage API tokens via admin UI
- [ ] **API-02**: External system can search users via `GET /api/v1/search?q=...` returning JSON
- [ ] **API-03**: External system can retrieve full user profile via `GET /api/v1/user/{email}`
- [ ] **API-04**: All API calls logged to audit trail with token identification
- [ ] **API-05**: Rate limiting prevents abuse with configurable per-token limits
- [ ] **API-06**: OpenAPI spec available at `/api/v1/docs`

### Workflow

- [ ] **WKFL-01**: Admin can generate onboarding checklist from job role mappings for a given job code
- [ ] **WKFL-02**: Admin can generate offboarding checklist that reverses all provisions
- [ ] **WKFL-03**: Each checklist item tracks completion status (who completed, when)
- [ ] **WKFL-04**: Dashboard shows active workflows with progress and overdue items

### Operational Hardening

- [x] **OPS-01**: Application exposes `/health` endpoint returning JSON status with database connectivity check
- [x] **OPS-02**: Every request gets a unique request ID propagated through all logs and async tasks
- [x] **OPS-03**: Application validates required configuration values at startup with clear error messages
- [x] **OPS-04**: Admin list views paginate tables with 100+ rows using offset/limit pattern

### Security Hardening

- [ ] **SEC-01**: `.whodis_salt` file removed from git history and properly gitignored
- [ ] **SEC-02**: CLI tool exists for safe encryption key rotation with dual-key migration and verification
- [ ] **SEC-03**: Search endpoint has per-user rate limiting to prevent abuse
- [x] **SEC-04**: Authentication header validation configurable for non-Azure environments

### Tech Debt

- [x] **DEBT-01**: Single application initialization path (consolidate `__init__.py` and `app_factory.py`)
- [x] **DEBT-02**: Deprecated `DataWarehouseService` removed, logic consolidated into `EmployeeProfilesRefreshService`
- [x] **DEBT-03**: Scheduled cleanup job removes expired search cache entries
- [x] **DEBT-04**: Asyncio patterns updated for Python 3.10+ compatibility (`get_running_loop`, `Runner`)

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### CI/CD

- **CI-01**: GitHub Actions CI workflow runs tests on every PR and blocks merge on failure
- **CI-02**: Automated deployment pipeline to Azure App Service

### Advanced Reporting

- **ARPT-01**: Email/Exchange mailbox analytics and mail flow reporting
- **ARPT-02**: Teams usage reports with call logs and membership tracking
- **ARPT-03**: SharePoint/OneDrive storage and activity reporting

### Advanced Automation

- **AUTO-01**: Onboarding checklist items auto-execute AD actions and license assignments
- **AUTO-02**: Self-service portal for common IT requests

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time chat integration | Not core to identity/operations mission |
| Mobile native app | Web responsive design sufficient for 4-5 user team |
| AI/ML features | Premature for current user base and scale |
| HR system integration | No HR API access available |
| Ticketing system integration | Requires ITSM vendor commitment not in place |
| Multi-tenant support | Single-organization deployment only |
| PowerBI/analytics embedding | Adds complexity without clear ROI for team size |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEST-01 | Phase 2 | Pending |
| TEST-02 | Phase 2 | Pending |
| TEST-03 | Phase 2 | Pending |
| TEST-04 | Phase 2 | Pending |
| PROF-01 | Phase 3 | Pending |
| PROF-02 | Phase 3 | Pending |
| PROF-03 | Phase 3 | Pending |
| PROF-04 | Phase 3 | Pending |
| PROF-05 | Phase 3 | Pending |
| PROF-06 | Phase 3 | Pending |
| SRCH-01 | Phase 3 | Pending |
| SRCH-02 | Phase 3 | Pending |
| COMP-01 | Phase 4 | Pending |
| COMP-02 | Phase 4 | Pending |
| COMP-03 | Phase 4 | Pending |
| COMP-04 | Phase 4 | Pending |
| COMP-05 | Phase 4 | Pending |
| REPT-01 | Phase 5 | Pending |
| REPT-02 | Phase 5 | Pending |
| REPT-03 | Phase 5 | Pending |
| REPT-04 | Phase 5 | Pending |
| REPT-05 | Phase 5 | Pending |
| REPT-06 | Phase 5 | Pending |
| REPT-07 | Phase 5 | Pending |
| REPT-08 | Phase 5 | Pending |
| WRIT-01 | Phase 6 | Pending |
| WRIT-02 | Phase 6 | Pending |
| WRIT-03 | Phase 6 | Pending |
| WRIT-04 | Phase 6 | Pending |
| WRIT-05 | Phase 6 | Pending |
| WRIT-06 | Phase 6 | Pending |
| WRIT-07 | Phase 6 | Pending |
| WRIT-08 | Phase 6 | Pending |
| API-01 | Phase 7 | Pending |
| API-02 | Phase 7 | Pending |
| API-03 | Phase 7 | Pending |
| API-04 | Phase 7 | Pending |
| API-05 | Phase 7 | Pending |
| API-06 | Phase 7 | Pending |
| WKFL-01 | Phase 8 | Pending |
| WKFL-02 | Phase 8 | Pending |
| WKFL-03 | Phase 8 | Pending |
| WKFL-04 | Phase 8 | Pending |
| OPS-01 | Phase 1 | Complete |
| OPS-02 | Phase 1 | Complete |
| OPS-03 | Phase 1 | Complete |
| OPS-04 | Phase 1 | Complete |
| SEC-01 | Phase 1 | Pending |
| SEC-02 | Phase 1 | Pending |
| SEC-03 | Phase 1 | Pending |
| SEC-04 | Phase 1 | Complete |
| DEBT-01 | Phase 1 | Complete |
| DEBT-02 | Phase 1 | Complete |
| DEBT-03 | Phase 1 | Complete |
| DEBT-04 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 52 total
- Mapped to phases: 52
- Unmapped: 0

---
*Requirements defined: 2026-04-24*
*Last updated: 2026-04-24 after roadmap creation*
