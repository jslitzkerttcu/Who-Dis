# Phase 8: Reporting - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins get a dedicated Reports section with org-wide dashboards — license utilization across all M365 SKUs, security posture (MFA adoption, failed sign-ins), and Genesys agent status. Report data is gathered via scheduled sync jobs (SandCastle job pattern from Phase 7), served from tiered caches, and exportable as CSV. Schedule management lives in the SandCastle portal; WhoDis shows run history.

Delivers REPT-01, REPT-02, REPT-03, REPT-04, REPT-05, REPT-06, REPT-07, REPT-08.

</domain>

<decisions>
## Implementation Decisions

### Report Navigation & Layout
- **D-01:** Report section structure is **Claude's discretion** — choose between dedicated tabbed page or sidebar sub-pages based on existing admin patterns.
- **D-02:** Each report view has **summary KPI cards at the top** (2-4 per report type) followed by the detailed data table below. Admins get headline numbers at a glance, then scroll for details.
- **D-03:** Failed sign-in report (REPT-04) has **both preset window buttons (24h / 7d / 30d) AND a custom date range picker** for edge cases.
- **D-04:** Each report tab gets its own **CSV export button** — reuses Phase 7 CSV export pattern with metadata header rows.

### Data Aggregation
- **D-05:** License dashboard (REPT-01/02) uses **full user iteration** via Graph `/users` with `$select=assignedLicenses,signInActivity` to build per-user license+activity data. This runs as a **scheduled sync job** (SandCastle job pattern), not on-demand, to keep daytime performance fast.
- **D-06:** MFA data collection approach is **Claude's discretion** — decide whether to bundle into the same user-iteration sync pass or run separately based on Graph API call patterns and efficiency.
- **D-07:** Failed sign-in data uses a **hybrid approach** — sync job caches recent failures (default window), date-range queries beyond the cached window fall back to Graph `/auditLogs/signIns` directly.
- **D-08:** Failed sign-in default view shows **last 72 hours**, paginated in the UI using the Phase 1 `paginate()` helper. The preset buttons and date picker let admins look further back.
- **D-09:** Genesys agent status (REPT-05) uses **live presence API** calls, **lazy-loaded** when the admin opens the Genesys tab. Matches the 5min freshness requirement without unnecessary background polling.

### Cache Strategy
- **D-10:** Report cache model is **Claude's discretion** — choose the best approach (new ReportCache model vs. extension of existing patterns) based on data shape and tiered TTL requirements (4h licenses, 1h security, 5min Genesys).
- **D-11:** Stale-cache indicator design is **Claude's discretion** — choose the simplest effective approach (timestamp + badge vs. auto-refresh notice).

### Report Scheduling (REPT-06/07)
- **D-12:** Report generation output is **Claude's discretion** — choose between cache-refresh-only or saved snapshots with history view, based on project goals and best practices. **Email delivery is explicitly excluded.**
- **D-13:** Schedule management lives in **SandCastle portal only** — report sync jobs registered in the job manifest alongside compliance_check and warehouse_sync. Portal handles cron scheduling.
- **D-14:** WhoDis shows a **run history view only** (read-only) — timestamp, status, duration from the job status API. No in-app schedule CRUD. REPT-06 is satisfied via portal scheduling + WhoDis history display.

### Claude's Discretion
- Report section structure (D-01): tabs vs. sidebar sub-pages
- MFA sync strategy (D-06): bundled or separate
- Cache model design (D-10): new table vs. pattern extension
- Stale-cache indicator (D-11): timestamp+badge vs. auto-refresh
- Report generation output type (D-12): cache-only vs. snapshots

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SandCastle Job Pattern (reference implementations — from Phase 7)
- `/Users/jslitzker/Repos/ProjectCrystalBall/src/api/v2/routers/jobs.py` — Job manifest schema, JOB_REGISTRY pattern, status polling endpoints
- `/Users/jslitzker/Repos/ProjectCrystalBall/src/api/v2/job_manager.py` — Thread-pool executor job manager with progress_callback
- `/Users/jslitzker/Repos/Queue-Tip/src/auth/keycloak_deps.py` — Portal M2M token validation (`azp=sandcastle-scheduler`)

### Existing WhoDis Services (extend, don't redesign)
- `app/services/graph_service.py` — `get_license_details()`, `get_subscribed_skus()`, `get_sign_in_logs()`, `get_authentication_methods()` — all already implemented in Phase 6
- `app/services/sku_catalog_cache.py` — Daily SKU GUID-to-friendly-name cache (Phase 6, Plan 02)
- `app/services/genesys_service.py` — Presence, queues, skills, routing status already returned
- `app/blueprints/admin/jobs.py` — Phase 7 jobs blueprint (manifest, trigger, status endpoints)

### Existing UI Patterns (reuse)
- Phase 7 CSV export pattern with metadata header rows
- Phase 1 `paginate()` helper + `render_pagination` Jinja macro for sign-in history tables
- Phase 6 HTMX lazy-load pattern for section-on-expand

### Requirements
- `.planning/REQUIREMENTS.md` §REPT-01..08 — Reporting requirements
- `.planning/ROADMAP.md` §"Phase 8: Reporting" — 6 success criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SkuCatalogCache` (`app/services/sku_catalog_cache.py`): daily subscribedSkus refresh — already resolves SKU GUIDs to friendly names for the license dashboard
- `GraphService.get_sign_in_logs()`: existing method for audit log queries — extend for batch/paginated retrieval
- `GraphService.get_license_details()` + `get_subscribed_skus()`: per-user and org-wide license data
- `GraphService.get_authentication_methods()`: per-user MFA method retrieval
- `GenesysCloudService`: presence, queues, skills already in `_process_user_data()` — expose for dashboard view
- Phase 7 `JobManagerService`: thread-pool executor with mutex, progress callback, SandCastle job manifest — reuse for report sync jobs
- Phase 1 `paginate()` helper: server-side pagination for sign-in history table

### Established Patterns
- SandCastle job registration: manifest endpoint + trigger + status polling (Phase 7)
- HTMX lazy-load on expand: `hx-get` + `hx-trigger="revealed"` (Phase 6)
- CSV export with metadata headers: first rows contain run context, then column headers + data (Phase 7)
- Background thread services: token refresh, Genesys cache, employee profiles, cache cleanup — same skeleton for report sync
- Client-side JS sort: Phase 7 established severity-ranked client-side table sorting

### Integration Points
- New routes in admin blueprint (or new reports sub-blueprint): `/admin/reports/`, per-report-type views
- New sync jobs registered in Phase 7 job manifest: `report_license_sync`, `report_security_sync`
- Report cache model/table for persisting aggregated snapshots with TTL
- Extend `container.py` with report service registrations

</code_context>

<specifics>
## Specific Ideas

- License dashboard KPI cards: Total SKUs, Total Assigned, Unused (30+ days no sign-in), Utilization %
- Security posture KPI cards: MFA Adoption %, Users Without MFA (count), Failed Sign-ins (last 24h)
- Genesys section lazy-loads live presence on tab open — no background polling needed
- Failed sign-in table default window: 72 hours, with presets (24h/7d/30d) and custom date range
- Sign-in history should be paginated for clean UI — not truncated to a handful of results
- Report sync jobs run during off-hours via SandCastle portal scheduling to minimize API load during business hours

</specifics>

<deferred>
## Deferred Ideas

- **SKU friendly-name tooltip on profile cards** — hover over SKU name in the M365 profile section shows the SKU description. Phase 6 UI refinement, not Phase 8 scope.
- **Email delivery of scheduled reports** — explicitly excluded per user decision. Revisit if demand emerges.
- **In-app schedule CRUD** — portal handles scheduling; no need for duplicate UI unless portal access becomes a bottleneck.

</deferred>

---

*Phase: 8-Reporting*
*Context gathered: 2026-05-17*
