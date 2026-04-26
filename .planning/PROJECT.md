# WhoDis v3.0 — IT Operations Platform

## What This Is

WhoDis is an enterprise identity lookup and IT operations platform for a small IT service desk team (~4-5 users). It provides unified search across Active Directory, Microsoft Graph, and Genesys Cloud with role-based access, encrypted configuration, comprehensive audit logging, and a modern HTMX+Tailwind UI. This milestone evolves WhoDis from a lookup tool into a production-grade IT operations platform with reporting, write operations, and API access.

## Core Value

IT staff can find everything they need to know about any employee — and act on it — from a single interface, without switching between AD, Azure portal, Genesys admin, or M365 admin center.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase. -->

- :white_check_mark: Multi-source concurrent search across LDAP, Graph, and Genesys — existing
- :white_check_mark: Azure AD SSO with role-based access control (viewer/editor/admin) — existing
- :white_check_mark: Encrypted configuration stored in PostgreSQL with Fernet encryption — existing
- :white_check_mark: Comprehensive audit logging of searches, access, config changes, and errors — existing
- :white_check_mark: Consolidated employee profiles with photo caching — existing
- :white_check_mark: Genesys blocked number management (CRUD) — existing
- :white_check_mark: Job role compliance module with warehouse integration — existing
- :white_check_mark: Session management with inactivity timeout and warnings — existing
- :white_check_mark: HTMX-powered hybrid UI with Tailwind CSS — existing
- :white_check_mark: Admin interface for user management, config editing, cache control, audit logs — existing
- :white_check_mark: Background token refresh and cache management — existing
- :white_check_mark: User notes for internal admin documentation — existing
- :white_check_mark: SandCastle containerized deployment with Docker, gunicorn, structured JSON logs, and `/health` / `/health/live` / `/health/ready` probes — Validated in Phase 3
- :white_check_mark: Fail-fast environment-variable configuration (DATABASE_URL, SECRET_KEY in production, Redis-backed Flask-Limiter) — Validated in Phase 3

### Active

<!-- Current scope. Building toward these. -->

**Testing & Reliability:**
- [ ] Automated test suite with pytest (unit + integration, 60%+ service coverage)
- [ ] CI workflow that runs tests on every PR and blocks merge on failure

**Expanded Data:**
- [ ] Profile cards show full Graph data (department, manager, licenses, MFA status, last sign-in)
- [ ] Profile cards show full Genesys data (queues, skills with proficiency, presence)
- [ ] Collapsible sections for extended data, lazy-loaded via HTMX
- [ ] Search result export to CSV and clipboard copy

**Compliance Hardening:**
- [ ] Job role compliance bulk check with progress indicators
- [ ] Compliance results exportable as CSV
- [ ] Warehouse sync with clear error messaging and last-sync display

**Reporting:**
- [ ] License utilization dashboard (SKU counts, unused licenses, cost waste)
- [ ] Sign-in activity and security posture report (MFA adoption, failed sign-ins)
- [ ] Genesys agent performance summary (presence, queues, status)
- [ ] Scheduled report generation (daily/weekly/monthly presets)

**Write Operations:**
- [ ] AD account actions from search results (unlock, password reset, enable/disable)
- [ ] License assignment and removal via Graph API
- [ ] Confirmation modals with mandatory reason text for all write operations

**API & Integration:**
- [ ] RESTful API with token-based auth using existing ApiToken model
- [ ] Read-only API endpoints for search, user profile, compliance status
- [ ] Rate limiting and OpenAPI documentation

**Workflow Automation:**
- [ ] Onboarding/offboarding checklists driven by job role compliance mappings
- [ ] Checklist completion tracking with audit trail

**Operational Hardening:**
- [x] Health check endpoint for monitoring and load balancer probes — Phase 3
- [ ] Request ID tracking through all logs and async tasks
- [x] Configuration validation on application startup — Phase 3 (DATABASE_URL / SECRET_KEY fail-fast)
- [ ] Admin pagination for tables with 100+ rows

**Security Hardening:**
- [ ] Remove .whodis_salt from git history
- [ ] Encryption key rotation tooling (dual-key migration with verification)
- [ ] Rate limiting on search endpoint (per-user)
- [ ] Header validation for non-Azure environments

**Tech Debt Cleanup:**
- [ ] Consolidate duplicate app init logic (__init__.py vs app_factory.py)
- [ ] Remove deprecated DataWarehouseService
- [ ] Implement search cache cleanup job
- [ ] Fix asyncio patterns for Python 3.10+ compatibility

### Out of Scope

<!-- Explicit boundaries. -->

- Real-time chat or messaging integration — not core to identity/operations mission
- Mobile native app — web-first, responsive design sufficient for team size
- AI/ML features (anomaly detection, NLP search) — premature for current scale
- HR system integration — no HR API access, not a current priority
- Ticketing system integration — would require ITSM vendor commitment
- Multi-tenant support — single-organization deployment only

## Context

- **Users:** 4-5 internal IT service desk staff with Admin/Editor/Viewer roles
- **Deployment:** SandCastle (Docker + Traefik) at `whodis.sandcastle.ttcu.com`; legacy Azure App Service path is being decommissioned post-Phase-9 verification
- **External APIs:** LDAP (AD), Microsoft Graph (beta), Genesys Cloud (OAuth2)
- **Codebase maturity:** v2.1.1 released, well-architected with DI container, interfaces, base service classes, middleware pipeline. Zero automated tests.
- **Key gap:** Profile cards underutilize available API data. No reporting, no write ops, no API.
- **Tech debt:** Duplicate init logic, deprecated services, asyncio compatibility issues
- **12 GitHub issues already created:** #13-#24 covering test suite, expanded profiles, compliance polish, search export, license dashboard, security posture report, Genesys performance, scheduled reports, AD actions, license management, REST API, onboarding checklists

## Constraints

- **Tech stack:** Flask/PostgreSQL/HTMX — extend existing patterns, don't introduce new frameworks
- **Auth:** Azure AD SSO only — all new endpoints must use existing auth decorators
- **Security:** All write operations require audit trail, confirmation workflows, and appropriate role checks
- **API permissions:** Graph API features may require additional Azure AD app permissions (document requirements per feature)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build on existing Flask/HTMX stack | Mature codebase with established patterns; team familiarity | -- Pending |
| Test suite before write operations | Write ops carry higher risk; tests provide safety net | -- Pending |
| Reports blueprint as shared foundation | License, security, and Genesys reports share infrastructure | -- Pending |
| Start API read-only | Reduce risk surface; write endpoints can layer on later | -- Pending |
| Operational hardening alongside features | Health check, request IDs, config validation are table stakes for production | -- Pending |

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
*Last updated: 2026-04-26 after Phase 3 (SandCastle Containerization & Deployment) closure*
