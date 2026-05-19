# WhoDis v4.0 — Platform Polish & Advanced Reporting

## What This Is

WhoDis is an enterprise identity lookup and IT operations platform for a small IT service desk team (~4-5 users). It provides unified search across Active Directory, Microsoft Graph, and Genesys Cloud with role-based access, encrypted configuration, comprehensive audit logging, and a modern HTMX+Tailwind UI. v3.0 delivered the full IT operations platform (reporting, write operations, REST API, workflow automation). This milestone polishes the platform with UX refinements, DevOps optimization, developer tooling, and expands reporting to Exchange, Teams, and SharePoint analytics.

## Core Value

IT staff can find everything they need to know about any employee — and act on it — from a single interface, without switching between AD, Azure portal, Genesys admin, or M365 admin center.

## Current Milestone: v4.0 Platform Polish & Advanced Reporting

**Goal:** Refine the existing platform with UX polish, DevOps optimization, developer tooling, and expand reporting to Exchange, Teams, and SharePoint analytics.

**Target features:**
- SKU friendly-name tooltips on profile cards
- Schema visualization (ER diagrams from live database metadata)
- Image size optimization (multi-stage Docker build)
- Advanced reporting (Exchange mailbox analytics, Teams usage/call logs, SharePoint/OneDrive storage)

## Requirements

### Validated

<!-- Shipped and confirmed valuable across v3.0 milestone. -->

- :white_check_mark: Multi-source concurrent search across LDAP, Graph, and Genesys — v1
- :white_check_mark: Keycloak OIDC SSO with role-based access control (viewer/editor/admin) — v3.0 Phase 4
- :white_check_mark: Encrypted configuration stored in PostgreSQL with Fernet encryption — v1
- :white_check_mark: Comprehensive audit logging of searches, access, config changes, and errors — v1
- :white_check_mark: Consolidated employee profiles with photo caching — v1
- :white_check_mark: Genesys blocked number management (CRUD) — v1
- :white_check_mark: Job role compliance module with warehouse integration — v1
- :white_check_mark: Session management with inactivity timeout and warnings — v1
- :white_check_mark: HTMX-powered hybrid UI with Tailwind CSS — v1
- :white_check_mark: Admin interface for user management, config editing, cache control, audit logs — v1
- :white_check_mark: Background token refresh and cache management — v1
- :white_check_mark: User notes for internal admin documentation — v1
- :white_check_mark: SandCastle containerized deployment with Docker, gunicorn, Traefik, structured JSON logs, health probes — v3.0 Phase 3
- :white_check_mark: Fail-fast env-var config (DATABASE_URL, SECRET_KEY, Redis-backed Flask-Limiter) — v3.0 Phase 3
- :white_check_mark: Automated test suite with pytest (60%+ coverage, pre-push hook) — v3.0 Phase 2
- :white_check_mark: Alembic schema migrations with auto-apply on container start — v3.0 Phase 5
- :white_check_mark: Enriched profile cards (Graph licenses, MFA, sign-in, Genesys queues/skills/presence) — v3.0 Phase 6
- :white_check_mark: Search export (CSV download + clipboard copy) — v3.0 Phase 6
- :white_check_mark: Compliance bulk check with progress, sortable results, CSV export, sync status — v3.0 Phase 7
- :white_check_mark: License/security/Genesys reporting with cached data and scheduling — v3.0 Phase 8
- :white_check_mark: AD write operations (unlock, password reset, enable/disable) with confirmation + audit — v3.0 Phase 9
- :white_check_mark: License assignment/removal/swap via Graph API — v3.0 Phase 9
- :white_check_mark: Token-authenticated REST API with rate limiting and OpenAPI docs — v3.0 Phase 10
- :white_check_mark: Onboarding/offboarding workflow checklists with completion tracking — v3.0 Phase 11

### Active

<!-- Current scope for v4.0. -->

**UX Polish:**
- [ ] SKU friendly-name tooltips on profile cards (hover shows license description)

**DevOps Optimization:**
- [ ] Multi-stage Docker build to reduce container image size

**Developer Tooling:**
- [ ] Schema visualization — ER diagrams generated from live database metadata

**Advanced Reporting:**
- [ ] Exchange mailbox analytics and mail flow reporting
- [ ] Teams usage reports with call logs and membership tracking
- [ ] SharePoint/OneDrive storage and activity reporting

### Out of Scope

<!-- Explicit boundaries. -->

- Real-time chat or messaging integration — not core to identity/operations mission
- Mobile native app — web-first, responsive design sufficient for team size
- AI/ML features (anomaly detection, NLP search) — premature for current scale
- HR system integration — no HR API access, not a current priority
- Ticketing system integration — would require ITSM vendor commitment
- Multi-tenant support — single-organization deployment only
- PowerBI/analytics embedding — adds complexity without clear ROI for team size
- CI/CD pipeline (GitHub Actions) — deferred from v3.0, not prioritized for v4.0
- Onboarding checklist auto-execution (AUTO-01) — deferred from v3.0
- Self-service portal (AUTO-02) — deferred from v3.0

## Context

- **Users:** 4-5 internal IT service desk staff with Admin/Editor/Viewer roles
- **Deployment:** SandCastle (Docker + Traefik) at `whodis.sandcastle.ttcu.com`
- **External APIs:** LDAP (AD), Microsoft Graph (beta), Genesys Cloud (OAuth2)
- **Codebase maturity:** v3.0 complete — 11 phases delivered, 40 plans executed, full IT operations platform with test suite, containerized deployment, OIDC auth, reporting, write ops, REST API, and workflow automation
- **Graph API permissions:** Advanced reporting (Exchange, Teams, SharePoint) will require additional Microsoft Graph API permissions — document requirements per feature
- **Docker image:** Currently functional but not size-optimized; multi-stage build will reduce footprint

## Constraints

- **Tech stack:** Flask/PostgreSQL/HTMX — extend existing patterns, don't introduce new frameworks
- **Auth:** Keycloak OIDC SSO — all new endpoints must use existing auth decorators
- **Security:** All new endpoints require audit trail and appropriate role checks
- **API permissions:** Graph API features require additional Azure AD app permissions (document requirements per feature)
- **Graph API scope:** Exchange/Teams/SharePoint reports require `Reports.Read.All` or equivalent — verify tenant consent before building

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build on existing Flask/HTMX stack | Mature codebase with established patterns; team familiarity | :white_check_mark: Good — validated across 11 phases |
| Test suite before write operations | Write ops carry higher risk; tests provide safety net | :white_check_mark: Good — 60%+ coverage gate enforced |
| Reports blueprint as shared foundation | License, security, and Genesys reports share infrastructure | :white_check_mark: Good — Phase 8 delivered cleanly |
| Start API read-only | Reduce risk surface; write endpoints can layer on later | :white_check_mark: Good — v1 API shipped read-only |
| Operational hardening alongside features | Health check, request IDs, config validation are table stakes | :white_check_mark: Good — all delivered in Phase 1+3 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-19 after v4.0 milestone initialization*
