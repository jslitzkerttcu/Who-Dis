# Roadmap: WhoDis v4.0

**Milestone:** WhoDis v4.0 — Platform Polish & Advanced Reporting
**Defined:** 2026-05-19
**Granularity:** Standard (5 phases — natural delivery boundaries from 7 requirement categories)
**Requirements:** 24 v1 requirements across 7 categories
**Continues from:** v3.0 (Phases 1-11 complete)

## Milestones

- v1.0-v3.0 (Phases 1-11) -- shipped 2026-05-19

## Phases

**Phase Numbering:**

- Integer phases (12, 13, ...): Planned milestone work (continues from v3.0 Phase 11)
- Decimal phases (12.1, 12.2): Urgent insertions if needed (marked with INSERTED)

- [ ] **Phase 12: UX Polish & DevOps** - SKU tooltips and Docker image optimization (zero external permissions needed)
- [ ] **Phase 13: Schema Visualization** - Live ER diagrams from database metadata for admin tooling
- [ ] **Phase 14: Reporting Infrastructure & Exchange** - CSV parsing foundation, freshness indicators, privacy detection, and Exchange mailbox/activity reports
- [ ] **Phase 15: Teams Reporting** - Teams usage, adoption trends, meeting analytics, and CSV export
- [ ] **Phase 16: SharePoint & OneDrive Reporting** - Site storage, OneDrive usage, sharing activity, growth trends, and CSV export

## Phase Details

### Phase 12: UX Polish & DevOps

**Goal**: Profile cards show human-readable license names on hover, and the Docker image is lean and cache-optimized for fast deployments
**Depends on**: Nothing (first phase of v4.0; builds on shipped v3.0 codebase)
**Requirements**: UXP-01, DEVOPS-01, DEVOPS-02, DEVOPS-03
**Success Criteria** (what must be TRUE):

  1. User hovers over any SKU badge on a profile card and sees the friendly license display name in a tooltip (not just the SKU GUID)
  2. Dockerfile uses a multi-stage build with separate builder and runtime stages, and the final image is at least 30% smaller than the current single-stage image
  3. `.dockerignore` excludes tests, docs, .planning, .git, __pycache__, and venv -- none of these appear in the runtime image
  4. Docker build layers are ordered so that `requirements.txt` installs before source code copy, enabling pip cache reuse when only source changes

**Plans**: 3 plans
Plans:
**Wave 1**

- [ ] 12-01-PLAN.md — SKU license tooltip (service plan extraction, humanization, template rendering)
- [ ] 12-02-PLAN.md — Docker multi-stage build optimization with healthcheck and .dockerignore

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 12-03-PLAN.md — Human verification checkpoint for tooltip and Docker

**UI hint**: yes

### Phase 13: Schema Visualization

**Goal**: Admins can explore the live database schema visually without leaving the WhoDis admin interface
**Depends on**: Phase 12
**Requirements**: SCHEMA-01, SCHEMA-02, SCHEMA-03
**Success Criteria** (what must be TRUE):

  1. Admin navigates to a dedicated admin page and sees an ER diagram showing all database tables, columns, and foreign key relationships
  2. The diagram renders as interactive SVG with zoom, pan, and clickable table nodes that highlight related tables
  3. The diagram is generated dynamically from live PostgreSQL metadata (information_schema or pg_catalog) -- not from a static file that could drift from reality

**Plans**: TBD
**UI hint**: yes

### Phase 14: Reporting Infrastructure & Exchange

**Goal**: The reporting subsystem can consume Graph usage report CSVs reliably, and admins can view Exchange mailbox and email activity analytics with freshness and privacy awareness
**Depends on**: Phase 12 (no code dependency on Phase 13; requires Reports.Read.All Azure AD permission granted before execution)
**Requirements**: RINF-01, RINF-02, RINF-03, RINF-04, EXCH-01, EXCH-02, EXCH-03, EXCH-04
**Success Criteria** (what must be TRUE):

  1. Graph usage report CSV responses (including 302 redirect chains) are fetched and parsed into structured data without errors
  2. Every report view displays a freshness indicator showing when the data was last updated, with a note that Microsoft reports have a 24-72 hour lag
  3. If the tenant has anonymized usernames in usage reports, the admin sees a clear warning explaining why names appear as hashed identifiers
  4. Report data is cached using the existing ReportCache pattern with a configurable TTL (default 4 hours)
  5. Admin can view a mailbox usage report showing storage size, item count, and last activity date per user, with inactive mailboxes (30+ days) visually highlighted
  6. Admin can view an email activity report showing send/receive counts per user over a configurable period and export either report as CSV

**Plans**: TBD
**UI hint**: yes

### Phase 15: Teams Reporting

**Goal**: Admins can view Teams adoption, usage, and meeting analytics from the same reporting interface, reusing the infrastructure built in Phase 14
**Depends on**: Phase 14 (reuses CSV parsing, caching, freshness, and privacy detection)
**Requirements**: TEAMS-01, TEAMS-02, TEAMS-03, TEAMS-04
**Success Criteria** (what must be TRUE):

  1. Admin can view a Teams usage report showing messages sent, meetings attended, and calls per user over a configurable period
  2. Admin can view active user counts and adoption trend lines over configurable periods (7/30/90/180 days)
  3. Meeting duration analytics show total hours and average duration per user
  4. Admin can export Teams usage data as CSV

**Plans**: TBD
**UI hint**: yes

### Phase 16: SharePoint & OneDrive Reporting

**Goal**: Admins can monitor storage consumption, file activity, and sharing behavior across SharePoint sites and OneDrive accounts, completing the M365 reporting story
**Depends on**: Phase 14 (reuses CSV parsing, caching, freshness, and privacy detection)
**Requirements**: SPOD-01, SPOD-02, SPOD-03, SPOD-04, SPOD-05
**Success Criteria** (what must be TRUE):

  1. Admin can view SharePoint site storage usage showing quota, used space, and file count per site
  2. Admin can view OneDrive storage usage per user showing quota and consumed space
  3. Report shows sharing activity breakdown distinguishing internal vs external sharing
  4. Admin can view storage growth trends over configurable periods (7/30/90/180 days)
  5. Admin can export SharePoint and OneDrive reports as CSV

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 12 -> 13 -> 14 -> 15 -> 16
(Phases 15 and 16 both depend on Phase 14 but not on each other; they execute sequentially for simplicity.)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 12. UX Polish & DevOps | 0/3 | Not started | - |
| 13. Schema Visualization | 0/0 | Not started | - |
| 14. Reporting Infrastructure & Exchange | 0/0 | Not started | - |
| 15. Teams Reporting | 0/0 | Not started | - |
| 16. SharePoint & OneDrive Reporting | 0/0 | Not started | - |

---
*Roadmap defined: 2026-05-19*
