# Requirements: WhoDis v4.0

**Defined:** 2026-05-19
**Core Value:** IT staff can find everything about any employee and act on it from a single interface

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### UX Polish

- [x] **UXP-01**: User can hover over any license SKU badge on a profile card and see the friendly display name in a tooltip

### DevOps Optimization

- [ ] **DEVOPS-01**: Dockerfile uses multi-stage build with builder and runtime stages, reducing image size by at least 30%
- [ ] **DEVOPS-02**: `.dockerignore` excludes all non-runtime files (tests, docs, .planning, .git, __pycache__, venv)
- [ ] **DEVOPS-03**: Docker build layers are ordered for optimal cache reuse (dependencies before source code)

### Schema Visualization

- [ ] **SCHEMA-01**: Admin can view an ER diagram of the live database schema on a dedicated admin page
- [ ] **SCHEMA-02**: ER diagram renders as interactive SVG with zoom, pan, and clickable table nodes
- [ ] **SCHEMA-03**: Diagram is generated from live PostgreSQL metadata, not a static file

### Exchange Reporting

- [ ] **EXCH-01**: Admin can view mailbox usage report showing storage size, item count, and last activity per user
- [ ] **EXCH-02**: Admin can view email activity report showing send/receive counts per user over a configurable period
- [ ] **EXCH-03**: Report highlights inactive mailboxes (no activity in 30+ days)
- [ ] **EXCH-04**: Admin can export Exchange reports as CSV

### Teams Reporting

- [ ] **TEAMS-01**: Admin can view Teams usage report showing messages sent, meetings attended, and calls per user
- [ ] **TEAMS-02**: Admin can view active user counts and adoption trends over configurable periods
- [ ] **TEAMS-03**: Report shows meeting duration analytics (total hours, average duration per user)
- [ ] **TEAMS-04**: Admin can export Teams reports as CSV

### SharePoint/OneDrive Reporting

- [ ] **SPOD-01**: Admin can view SharePoint site storage usage showing quota, used space, and file count per site
- [ ] **SPOD-02**: Admin can view OneDrive storage usage per user with quota and consumed space
- [ ] **SPOD-03**: Report shows sharing activity breakdown (internal vs external sharing)
- [ ] **SPOD-04**: Admin can view storage growth trends over configurable periods
- [ ] **SPOD-05**: Admin can export SharePoint/OneDrive reports as CSV

### Reporting Infrastructure

- [ ] **RINF-01**: Graph usage report CSV responses are parsed correctly (handling 302 redirects)
- [ ] **RINF-02**: Report data displays a freshness indicator showing when data was last updated (24-72hr lag documented)
- [ ] **RINF-03**: Tenant privacy setting is detected and admin is warned if usernames are concealed in reports
- [ ] **RINF-04**: All report data is cached with configurable TTL (default 4 hours) using existing ReportCache pattern

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### CI/CD

- **CI-01**: GitHub Actions CI workflow runs tests on every PR and blocks merge on failure
- **CI-02**: Automated deployment pipeline to Azure App Service

### Advanced Automation

- **AUTO-01**: Onboarding checklist items auto-execute AD actions and license assignments
- **AUTO-02**: Self-service portal for common IT requests

### Advanced Teams Analytics

- **TEAMS-ADV-01**: Individual call quality records via CallRecords API (requires webhook infrastructure)

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
| Teams call quality (individual records) | Requires webhook infrastructure -- deferred to v2 |
| Exchange forwarding rule detection | N+1 API calls per user -- not scalable for bulk reports |
| Cross-report correlation dashboard | Premature optimization -- build individual reports first |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| UXP-01 | Phase 12 | Complete |
| DEVOPS-01 | Phase 12 | Pending |
| DEVOPS-02 | Phase 12 | Pending |
| DEVOPS-03 | Phase 12 | Pending |
| SCHEMA-01 | Phase 13 | Pending |
| SCHEMA-02 | Phase 13 | Pending |
| SCHEMA-03 | Phase 13 | Pending |
| RINF-01 | Phase 14 | Pending |
| RINF-02 | Phase 14 | Pending |
| RINF-03 | Phase 14 | Pending |
| RINF-04 | Phase 14 | Pending |
| EXCH-01 | Phase 14 | Pending |
| EXCH-02 | Phase 14 | Pending |
| EXCH-03 | Phase 14 | Pending |
| EXCH-04 | Phase 14 | Pending |
| TEAMS-01 | Phase 15 | Pending |
| TEAMS-02 | Phase 15 | Pending |
| TEAMS-03 | Phase 15 | Pending |
| TEAMS-04 | Phase 15 | Pending |
| SPOD-01 | Phase 16 | Pending |
| SPOD-02 | Phase 16 | Pending |
| SPOD-03 | Phase 16 | Pending |
| SPOD-04 | Phase 16 | Pending |
| SPOD-05 | Phase 16 | Pending |

**Coverage:**

- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---
*Requirements defined: 2026-05-19*
*Traceability updated: 2026-05-19 -- all 24 requirements mapped to Phases 12-16*
