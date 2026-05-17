# Phase 8: Reporting - Research

**Researched:** 2026-05-17
**Domain:** Dashboard reporting (Graph API license/security data, Genesys presence, caching, SandCastle job integration)
**Confidence:** HIGH

## Summary

Phase 8 builds an admin Reports section with four tabs: License Utilization, Security Posture, Contact Center Status, and Run History. The implementation extends existing services (GraphService, GenesysCloudService) with new bulk data-fetching methods, introduces a report cache model for tiered TTL storage, registers new sync jobs in the SandCastle job manifest, and creates report-specific templates following the HTMX tab pattern defined in the UI-SPEC.

The critical Graph API finding is that MFA status should NOT use per-user `authentication/methods` iteration for bulk reporting. Microsoft provides a dedicated bulk endpoint (`/reports/authenticationMethods/userRegistrationDetails`) that returns `isMfaRegistered` and `isMfaCapable` for all users in a single paginated call. This is significantly more efficient and is the officially recommended approach. For license utilization, the existing `/subscribedSkus` endpoint provides org-level counts, while per-user license+signInActivity data requires paginated iteration over `/users?$select=displayName,userPrincipalName,assignedLicenses,signInActivity` (max 500 per page when signInActivity is included).

**Primary recommendation:** Use the Graph bulk reporting endpoints (userRegistrationDetails for MFA, subscribedSkus + users iteration for licenses), store aggregated results in a new `report_cache` table with tiered TTLs, and register two new SandCastle jobs (`report_license_sync`, `report_security_sync`) following the Phase 7 job pattern exactly.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-02: Each report view has summary KPI cards at top (2-4 per type) followed by detailed data table
- D-03: Failed sign-in report has both preset window buttons (24h/7d/30d) AND custom date range picker
- D-04: Each report tab gets its own CSV export button -- reuses Phase 7 CSV export pattern with metadata header rows
- D-05: License dashboard uses full user iteration via Graph `/users` with `$select=assignedLicenses,signInActivity` as a scheduled sync job (SandCastle pattern), not on-demand
- D-07: Failed sign-in data uses hybrid approach -- sync job caches recent failures, date-range queries beyond cached window fall back to Graph `/auditLogs/signIns` directly
- D-08: Failed sign-in default view shows last 72 hours, paginated using Phase 1 `paginate()` helper
- D-09: Genesys agent status uses live presence API calls, lazy-loaded when admin opens Genesys tab (5min freshness, no background polling)
- D-13: Schedule management lives in SandCastle portal only -- jobs registered in manifest alongside compliance_check and warehouse_sync
- D-14: WhoDis shows run history view only (read-only) -- timestamp, status, duration from job status API. No in-app schedule CRUD

### Claude's Discretion
- D-01: Report section structure -- tabs vs. sidebar sub-pages (UI-SPEC chose tabs)
- D-06: MFA sync strategy -- bundled or separate from license sync
- D-10: Cache model design -- new table vs. pattern extension
- D-11: Stale-cache indicator -- timestamp+badge vs. auto-refresh (UI-SPEC chose timestamp+badge)
- D-12: Report generation output type -- cache-only vs. snapshots

### Deferred Ideas (OUT OF SCOPE)
- SKU friendly-name tooltip on profile cards (Phase 6 UI refinement)
- Email delivery of scheduled reports (explicitly excluded)
- In-app schedule CRUD (portal handles scheduling)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REPT-01 | License utilization dashboard with all M365 SKUs, assigned/available/consumed counts | Graph `/subscribedSkus` for org totals + `/users?$select=assignedLicenses,signInActivity` for per-user data; SkuCatalogCache for friendly names |
| REPT-02 | Unused licenses (no sign-in 30+ days) with utilization % per SKU | signInActivity.lastSignInDateTime from user iteration; compare against 30-day threshold during sync job |
| REPT-03 | MFA adoption rate as % with list of non-MFA users | Graph `/reports/authenticationMethods/userRegistrationDetails` bulk endpoint; `isMfaRegistered` field |
| REPT-04 | Failed sign-in table filterable by date range | Graph `/auditLogs/signIns` with `$filter=createdDateTime ge/le`; hybrid cache + live query pattern |
| REPT-05 | Genesys presence, routing status, queue memberships | Genesys `/api/v2/users/search` with presence expand or `/api/v2/analytics/users/observations/query` |
| REPT-06 | Create/edit/delete report schedules (daily/weekly/monthly) | Satisfied via SandCastle portal scheduling + WhoDis run history display (D-13/D-14) |
| REPT-07 | Reports generate on schedule with history view | JobManagerService + JobRun model for execution; job_runs table queried for history tab |
| REPT-08 | Report data cached with configurable TTL (4h licenses, 1h security, 5min Genesys) | New ReportCache model with tiered TTL; stale indicator in UI |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| License data aggregation | API / Backend (sync job) | Database / Storage (cache) | Scheduled Graph API calls aggregate into cache; UI reads from cache |
| MFA status aggregation | API / Backend (sync job) | Database / Storage (cache) | Bulk Graph endpoint fetched during sync, stored in report cache |
| Failed sign-in display | API / Backend (route) | Database / Storage (cache + live fallback) | Hybrid: cached recent data + live Graph query for custom ranges |
| Genesys presence | API / Backend (route) | -- | Live API call per request; no caching (5min freshness via lazy-load) |
| Report scheduling | External (SandCastle portal) | API / Backend (manifest) | Portal owns CRUD; WhoDis only exposes manifest + trigger endpoints |
| Run history display | Frontend Server (SSR) | Database / Storage (job_runs) | Jinja2 renders from job_runs table data |
| CSV export | API / Backend (route) | -- | Server generates CSV from cached data, streams as download |
| Stale-cache indicator | Frontend Server (SSR) | -- | Template checks cache timestamp against TTL, renders badge |

## Standard Stack

### Core (already in project -- no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 | Web framework, blueprint routes | Project standard [VERIFIED: requirements.txt] |
| SQLAlchemy | 2.0.45 | ORM for report cache model, queries | Project standard [VERIFIED: requirements.txt] |
| requests | 2.33.0 | HTTP client for Graph/Genesys API calls | Project standard [VERIFIED: requirements.txt] |
| msal | 1.34.0 | Graph API token acquisition | Project standard [VERIFIED: requirements.txt] |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| csv (stdlib) | -- | CSV export generation | Per-tab CSV export (D-04) |
| io (stdlib) | -- | StringIO for CSV buffering | CSV response streaming |
| datetime (stdlib) | -- | TTL calculations, date range filtering | Cache freshness checks |
| concurrent.futures (stdlib) | -- | ThreadPoolExecutor for sync jobs | JobManagerService pattern |

### No New Dependencies
This phase requires **zero new packages**. All functionality is built on existing Flask/SQLAlchemy/requests/msal stack plus Python stdlib. The Graph API and Genesys API calls use the existing `_make_request` / `_handle_response` pattern from `BaseAPIService`.

## Package Legitimacy Audit

No new packages to audit. All dependencies are already in `requirements.txt` and verified via prior phases.

## Architecture Patterns

### System Architecture Diagram

```
SandCastle Portal                WhoDis Flask App
+------------------+            +----------------------------------------+
| Scheduler (cron) |---POST---->| /api/v2/admin/jobs/{name}              |
|                  |            |   -> JobManagerService.start_job()      |
| - report_license |            |     -> ReportLicenseSyncJob.run()       |
| - report_security|            |       -> GraphService (paginated)       |
+------------------+            |       -> ReportCache.store()            |
                                |                                         |
Admin Browser                   |                                         |
+------------------+            |                                         |
| /admin/reports   |---GET----->| reports blueprint (tab routing)         |
| ?tab=licenses    |            |   -> ReportCache.get("license_summary") |
|                  |<--HTML-----|   -> render_template(partial)           |
|                  |            |                                         |
| ?tab=security    |---GET----->|   -> ReportCache.get("mfa_summary")     |
|                  |            |   -> ReportCache.get("signin_failures") |
|                  |            |                                         |
| ?tab=genesys     |---GET----->|   -> GenesysCloudService (live)         |
| (lazy-load)      |<--HTML-----|   -> render_template(partial)           |
|                  |            |                                         |
| ?tab=history     |---GET----->|   -> JobRun.query (read DB)             |
|                  |<--HTML-----|   -> render_template(partial)           |
|                  |            |                                         |
| Export CSV       |---GET----->|   -> ReportCache.get() -> csv.writer    |
|                  |<--CSV------|   -> Response(Content-Disposition)      |
+------------------+            +----------------------------------------+
                                          |
                                   +------+------+
                                   | PostgreSQL  |
                                   | report_cache|
                                   | job_runs    |
                                   +-------------+
```

### Recommended Project Structure
```
app/
├── blueprints/
│   └── admin/
│       ├── reports.py              # NEW: Report tab routes + CSV export
│       └── __init__.py             # MODIFY: Register report routes
├── services/
│   ├── graph_service.py            # MODIFY: Add bulk user/MFA/signIn methods
│   ├── genesys_service.py          # MODIFY: Add bulk presence method
│   └── report_sync_service.py      # NEW: Sync job runner for license+security
├── models/
│   └── report_cache.py             # NEW: ReportCache model (tiered TTL)
├── templates/
│   └── admin/
│       ├── reports.html            # NEW: Reports page shell + tab nav
│       └── partials/
│           ├── _report_licenses.html    # NEW: License tab content
│           ├── _report_security.html    # NEW: Security tab content
│           ├── _report_genesys.html     # NEW: Contact center tab content
│           ├── _report_history.html     # NEW: Run history tab content
│           └── _report_stale_badge.html # NEW: Stale-cache indicator partial
├── static/
│   └── js/
│       └── compliance-sort.js      # REUSE: Client-side table sorting
└── container.py                    # MODIFY: Register report_sync_service
```

### Pattern 1: Report Cache Model (D-10 Recommendation)

**What:** New `report_cache` table storing pre-aggregated report data as JSONB with tiered TTLs.
**When to use:** Any report tab that reads from cached sync data (licenses, security).
**Why new table vs. ExternalServiceData:** Report data is aggregated summaries (KPI totals, user lists), not raw service records. Different shape, different TTL semantics, different query patterns. A dedicated model avoids overloading ExternalServiceData.

```python
# Source: Derived from ExternalServiceData + SyncMetadata patterns [VERIFIED: codebase]
class ReportCache(BaseModel, TimestampMixin):
    __tablename__ = "report_cache"

    report_type = db.Column(db.String(50), nullable=False, index=True)
    # e.g., "license_summary", "license_per_sku", "mfa_summary",
    #        "mfa_users_without", "signin_failures"
    cache_key = db.Column(db.String(100), nullable=False, index=True)
    data = db.Column(db.JSON, nullable=False)  # Aggregated report data
    generated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ttl_hours = db.Column(db.Integer, nullable=False)  # 4 for licenses, 1 for security

    __table_args__ = (
        db.UniqueConstraint("report_type", "cache_key", name="uq_report_cache"),
    )

    @property
    def is_stale(self) -> bool:
        from datetime import datetime, timezone, timedelta
        if not self.generated_at:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.ttl_hours)
        return self.generated_at < cutoff
```

### Pattern 2: Extending Graph Service for Bulk Operations

**What:** New methods on GraphService for paginated user iteration and bulk MFA reporting.
**When to use:** Sync jobs need org-wide data that the existing per-user methods don't provide.

```python
# Source: Microsoft Graph API docs [CITED: learn.microsoft.com/graph/api/user-list]
def get_all_users_with_licenses(self) -> List[Dict[str, Any]]:
    """Paginate through all users with license+signIn data.

    Uses /beta/users?$select=displayName,userPrincipalName,
    assignedLicenses,signInActivity&$top=500
    Max page size is 500 when signInActivity is selected.
    Requires: User.Read.All + AuditLog.Read.All permissions.
    """
    token = self.get_access_token()
    if not token:
        return []

    all_users = []
    url = (
        f"{self.graph_base_url}/users"
        "?$select=displayName,userPrincipalName,assignedLicenses,signInActivity"
        "&$top=500"
        "&$filter=assignedLicenses/$count ne 0"
        "&$count=true"
    )
    headers = self._get_headers(token)
    headers["ConsistencyLevel"] = "eventual"  # Required for $count

    while url:
        response = self._make_request("GET", url, token, headers=headers)
        data = self._handle_response(response)
        if not data:
            break
        all_users.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return all_users
```

```python
# Source: Microsoft Graph API docs [CITED: learn.microsoft.com/graph/api/authenticationmethodsroot-list-userregistrationdetails]
def get_mfa_registration_details(self) -> List[Dict[str, Any]]:
    """Bulk MFA registration status for all users.

    Uses /v1.0/reports/authenticationMethods/userRegistrationDetails
    Requires: AuditLog.Read.All permission.
    Much more efficient than per-user authentication/methods iteration.
    """
    token = self.get_access_token()
    if not token:
        return []

    all_details = []
    url = (
        "https://graph.microsoft.com/v1.0"
        "/reports/authenticationMethods/userRegistrationDetails"
    )

    while url:
        response = self._make_request("GET", url, token)
        data = self._handle_response(response)
        if not data:
            break
        all_details.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return all_details
```

### Pattern 3: SandCastle Job Registration

**What:** Extend JOB_REGISTRY in `jobs.py` with two new report sync jobs.
**When to use:** Report data needs scheduled refresh.

```python
# Source: Existing jobs.py JOB_REGISTRY pattern [VERIFIED: codebase]
{
    "name": "report_license_sync",
    "display_name": "License Report Sync",
    "description": "Sync license utilization data from Graph API",
    "endpoint": "/api/v2/admin/jobs/report_license_sync",
    "default_cron": "0 4 * * *",    # 4 AM daily
    "timeout_seconds": 600,
    "method": "POST",
    "dependencies": [],
},
{
    "name": "report_security_sync",
    "display_name": "Security Report Sync",
    "description": "Sync MFA and sign-in failure data from Graph API",
    "endpoint": "/api/v2/admin/jobs/report_security_sync",
    "default_cron": "0 * * * *",     # Hourly
    "timeout_seconds": 300,
    "method": "POST",
    "dependencies": [],
},
```

### Pattern 4: Hybrid Sign-In Query (D-07)

**What:** Cached recent failures served from DB; custom date ranges fall back to live Graph API.
**When to use:** Failed sign-in tab with date range picker.

```python
# Pseudocode for the hybrid approach
def get_failed_signins(self, window=None, from_date=None, to_date=None):
    """Serve from cache for default/preset windows; live query for custom ranges."""
    if window in ("24h", "72h", "7d"):
        # Serve from report_cache (populated by security sync job)
        cache = ReportCache.query.filter_by(
            report_type="signin_failures", cache_key="recent"
        ).first()
        if cache and not cache.is_stale:
            return filter_by_window(cache.data, window)
    # Custom range or stale cache -> live Graph query
    return self._query_graph_signins(from_date, to_date)
```

### Pattern 5: Genesys Bulk Presence (D-09)

**What:** Fetch all Genesys users with presence on-demand when Contact Center tab loads.
**When to use:** Genesys tab lazy-load via HTMX `hx-trigger="revealed"`.

```python
# Source: Genesys API docs [CITED: developer.genesys.cloud]
def get_all_agents_presence(self) -> List[Dict[str, Any]]:
    """Get all Genesys users with presence, routing status, and queues.

    Uses POST /api/v2/users/search with expand=routingStatus,presence
    plus GET /api/v2/routing/queues/{id}/members for queue memberships.
    """
    token = self.get_access_token()
    if not token:
        return []

    search_payload = {
        "query": [{"type": "EXACT", "fields": ["state"], "values": ["active"]}],
        "expand": ["routingStatus", "presence"],
        "pageSize": 100,
        "pageNumber": 1,
    }
    # Paginate through all active users
    # Process presence from presenceDefinition.systemPresence
    # Process routing from routingStatus.status
```

### Anti-Patterns to Avoid
- **Per-user MFA iteration for dashboards:** Microsoft explicitly recommends using `/reports/authenticationMethods/userRegistrationDetails` for bulk MFA reporting, not iterating `authentication/methods` per user. The existing `get_authentication_methods()` is for individual profile cards only.
- **On-demand license data aggregation:** With potentially hundreds of users, iterating Graph API on each page load would be slow and hit rate limits. Always serve from cache (D-05).
- **Background polling for Genesys presence:** D-09 specifies lazy-load on tab open. No background thread needed -- the 5min freshness comes naturally from the fact that data is fetched live each time the tab opens.
- **Storing raw API responses in cache:** Store pre-aggregated KPIs and filtered lists. The sync job does the computation; the route handler just reads and renders.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph API pagination | Manual nextLink following | Reusable `_paginate_graph()` helper on GraphService | @odata.nextLink pattern is identical across all Graph endpoints |
| CSV export | Custom CSV generation per report | Extend Phase 7 `_csv_safe()` + `csv.writer` pattern | Consistent metadata headers, CSV injection prevention |
| Pagination UI | Custom pagination for sign-in table | `paginate()` helper + `render_pagination` macro | Already proven across 4 admin views |
| Client-side sorting | New sort implementation | Reuse `compliance-sort.js` with `data-sort-column` attributes | Phase 7 established the pattern |
| Date range filtering | Custom date parsing | Standard `datetime.fromisoformat()` + `$filter` OData syntax | Graph API has standard OData filter format |
| Job execution | Custom background thread | `JobManagerService.start_job()` | Conflict detection, status tracking, app context propagation |
| Cache staleness check | Per-route timestamp comparison | `ReportCache.is_stale` property | Centralized TTL logic in model |

**Key insight:** This phase is primarily a data aggregation + display phase. Every infrastructure component (jobs, caching, pagination, CSV, sorting) already exists in the codebase from prior phases. The new code is: (1) Graph API methods for bulk data, (2) a sync job that aggregates, (3) a cache model, and (4) template partials.

## Common Pitfalls

### Pitfall 1: Graph API Rate Limiting During User Iteration
**What goes wrong:** Iterating all users with `signInActivity` hits Graph throttling (429 responses) for large tenants.
**Why it happens:** `signInActivity` triggers a different internal store in Entra ID with stricter rate limits. Max page size drops to 500 (vs 999 normal).
**How to avoid:** Run sync during off-hours (D-05 specifies SandCastle scheduling). Add retry-after handling in pagination loop. Use `$top=500` explicitly.
**Warning signs:** HTTP 429 responses, incomplete user lists in cache.

### Pitfall 2: signInActivity Requires Entra ID P1/P2 License
**What goes wrong:** `signInActivity` returns null for tenants without P1/P2 licensing.
**Why it happens:** This is a premium feature requiring specific Azure AD license tier.
**How to avoid:** The sync job should handle null `signInActivity` gracefully -- treat as "unknown" rather than "inactive". Log a warning if all users return null.
**Warning signs:** Every user shows "N/A" for last sign-in.

### Pitfall 3: MFA Endpoint Returns Only Members by Default
**What goes wrong:** Guest users may or may not be included in `userRegistrationDetails` depending on tenant config.
**Why it happens:** Default scope may include or exclude guests.
**How to avoid:** Filter with `$filter=userType eq 'member'` to be explicit about which users count toward MFA adoption percentage.
**Warning signs:** MFA adoption % seems wrong because guest accounts are diluting the denominator.

### Pitfall 4: Sign-In Logs Retention Limits
**What goes wrong:** Graph `/auditLogs/signIns` only retains data for 30 days (P1) or 30 days (P2) by default.
**Why it happens:** Azure AD sign-in log retention is license-dependent.
**How to avoid:** The 30d preset button should work within retention. For custom ranges, handle Graph returning empty results gracefully with a user-friendly message ("Sign-in data is only available for the last 30 days").
**Warning signs:** Custom date range queries returning empty for dates beyond retention window.

### Pitfall 5: Genesys `presence` Expand Not Available on Search
**What goes wrong:** The `/api/v2/users/search` endpoint may not support `presence` in the expand parameter.
**Why it happens:** Presence is a real-time attribute, not stored with user records. Search returns user metadata, not live state.
**How to avoid:** Use the Analytics observation API (`POST /api/v2/analytics/users/observations/query`) for bulk presence, or fetch presence individually per user via `GET /api/v2/users/{id}/presencedefinitions`. For a small Genesys roster (context says ~4-5 IT users, but could be larger contact center), individual presence lookups may be acceptable.
**Warning signs:** `presence` field is null or missing from search results even when user is online.

### Pitfall 6: ConsistencyLevel Header for $count Queries
**What goes wrong:** Graph API returns 400 when using `$count=true` or `$filter` with `/$count` without the `ConsistencyLevel: eventual` header.
**Why it happens:** Advanced query capabilities require opt-in via this header on the beta endpoint.
**How to avoid:** Always include `ConsistencyLevel: eventual` header when using `$count` in user queries.
**Warning signs:** HTTP 400 with "Unsupported query" error message.

## Code Examples

### CSV Export Route (reusing Phase 7 pattern)
```python
# Source: Phase 7 compliance export pattern [VERIFIED: codebase job_role_compliance.py:647]
@require_role("admin")
def export_license_csv():
    cache = ReportCache.query.filter_by(
        report_type="license_summary", cache_key="per_sku"
    ).first()
    if not cache:
        abort(404)

    output = io.StringIO()
    writer = csv.writer(output)

    # Metadata rows (Phase 7 pattern)
    writer.writerow([f"Report: License Utilization"])
    writer.writerow([f"Generated: {cache.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"])
    writer.writerow([])

    # Header row
    writer.writerow(["SKU Name", "Assigned", "Available", "Consumed",
                      "Utilization %", "Unused (30d)"])

    # Data rows
    for sku in cache.data:
        writer.writerow([
            _csv_safe(sku["name"]),
            sku["assigned"],
            sku["available"],
            sku["consumed"],
            f"{sku['utilization_pct']:.1f}%",
            sku["unused_30d"],
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=license_utilization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        },
    )
```

### Tab Routing with HTMX
```python
# Source: Derived from existing admin blueprint patterns [VERIFIED: codebase]
@require_role("admin")
def reports():
    """Main reports page with tab navigation."""
    tab = request.args.get("tab", "licenses")
    if request.headers.get("HX-Request"):
        # HTMX partial request -- return tab content only
        return _render_tab(tab)
    # Full page request
    return render_template("admin/reports.html", active_tab=tab)

def _render_tab(tab: str):
    handlers = {
        "licenses": _render_licenses_tab,
        "security": _render_security_tab,
        "genesys": _render_genesys_tab,
        "history": _render_history_tab,
    }
    handler = handlers.get(tab)
    if not handler:
        abort(404)
    return handler()
```

### Stale-Cache Check in Template
```jinja2
{# Source: Derived from _warehouse_sync_status.html pattern [VERIFIED: codebase] #}
{% if cache_entry and not cache_entry.is_stale %}
  <div class="flex items-center text-sm">
    <i class="fas fa-clock text-green-500 mr-2"></i>
    <span class="text-gray-500">Updated {{ cache_entry.generated_at | timeago }}</span>
  </div>
{% elif cache_entry %}
  <div class="flex items-center text-sm">
    <i class="fas fa-clock text-yellow-500 mr-2"></i>
    <span class="text-yellow-600 font-semibold">Data is {{ cache_entry.generated_at | timeago }} old</span>
    <button hx-post="/admin/reports/refresh/{{ report_type }}"
            class="ml-2 text-blue-600 hover:text-blue-800 text-sm font-semibold">
      Refresh Data
    </button>
  </div>
{% endif %}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-user `authentication/methods` for MFA | `/reports/authenticationMethods/userRegistrationDetails` bulk endpoint | GA in Graph v1.0 (2023) | Orders of magnitude fewer API calls for MFA reporting |
| Graph v1.0 for signInActivity | Graph beta required for signInActivity on user list | Ongoing (beta only) | Must use beta endpoint for user iteration with sign-in data |
| Manual SKU GUID lookup | SkuCatalogCache (Phase 6) | Phase 6 | Already solved -- reuse existing cache |

**Deprecated/outdated:**
- `credentialUserRegistrationCount` (beta only) -- superseded by v1.0 `userRegistrationDetails`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Genesys `/api/v2/users/search` supports `presence` in expand parameter for bulk queries | Architecture Patterns / Pitfall 5 | May need to fall back to per-user presence lookups or Analytics observation API |
| A2 | Tenant has Entra ID P1/P2 license for signInActivity and MFA reports | Pitfalls 2 | License dashboard would lack sign-in data; MFA report endpoint may not work |
| A3 | Sign-in log retention is 30 days in target tenant | Pitfall 4 | Custom date ranges beyond retention return empty data |
| A4 | Genesys agent roster is small enough for per-user presence if search expand fails | Pitfall 5 | Large rosters would need batch Analytics API approach |

## Open Questions (RESOLVED)

1. **Genesys presence API approach** (RESOLVED — implement with search expand + per-user fallback)
   - What we know: The search endpoint returns presence from `presenceDefinition.systemPresence` in existing code, but this may only work for individual user lookups with expand
   - What's unclear: Whether bulk search with `presence` expand returns real-time presence or requires separate API calls
   - Recommendation: Implement with search expand first; add fallback to per-user GET if presence is null in search results

2. **MFA reporting endpoint licensing** (RESOLVED — graceful degradation on 403)
   - What we know: `userRegistrationDetails` requires Entra ID P1/P2
   - What's unclear: Whether the target tenant has this license tier
   - Recommendation: Implement with graceful degradation -- if endpoint returns 403, show "MFA data requires Entra ID P1/P2 license" message

3. **D-06: Bundle MFA with license sync or run separately?**
   - Research recommendation: **Run separately.** License sync iterates all users (slow, 4h TTL). MFA uses a single bulk endpoint (fast, 1h TTL). Different cadences and different API patterns. Two separate jobs (`report_license_sync` at 4h, `report_security_sync` at 1h) avoids coupling and allows independent scheduling.

4. **D-10: Cache model design recommendation**
   - Research recommendation: **New `report_cache` table.** ExternalServiceData stores raw service records with `service_name/data_type/service_id` schema. Report data is aggregated summaries (JSON blobs of KPIs and user lists). Different shape, different TTL semantics. A dedicated table is cleaner and avoids polluting the existing model.

5. **D-12: Report generation output recommendation**
   - Research recommendation: **Cache-refresh-only (no snapshots).** Report sync jobs update the `report_cache` table. Historical data lives in `job_runs` (execution history). Snapshots would add storage complexity for minimal benefit -- admins care about current state, not point-in-time history.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3+ (in requirements-dev.txt) |
| Config file | none (implicit discovery) |
| Quick run command | `pytest tests/unit/ -x -q` |
| Full suite command | `pytest tests/ -v --cov=app` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REPT-01 | License sync job aggregates SKU data correctly | unit | `pytest tests/unit/services/test_report_sync_service.py::test_license_sync -x` | Wave 0 |
| REPT-02 | Unused licenses detected (30d threshold) | unit | `pytest tests/unit/services/test_report_sync_service.py::test_unused_license_detection -x` | Wave 0 |
| REPT-03 | MFA summary computed from userRegistrationDetails | unit | `pytest tests/unit/services/test_report_sync_service.py::test_mfa_sync -x` | Wave 0 |
| REPT-04 | Failed sign-in hybrid query (cache + live fallback) | unit | `pytest tests/unit/services/test_report_sync_service.py::test_signin_hybrid -x` | Wave 0 |
| REPT-05 | Genesys presence data parsed correctly | unit | `pytest tests/unit/services/test_genesys_service.py::test_agents_presence -x` | Wave 0 |
| REPT-06 | Job manifest includes report sync jobs | unit | `pytest tests/unit/test_jobs_manifest.py -x` | Wave 0 |
| REPT-07 | Run history query returns formatted results | unit | `pytest tests/unit/test_report_routes.py::test_history_tab -x` | Wave 0 |
| REPT-08 | ReportCache.is_stale respects TTL | unit | `pytest tests/unit/models/test_report_cache.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/ -x -q`
- **Per wave merge:** `pytest tests/ -v --cov=app`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/services/test_report_sync_service.py` -- covers REPT-01..04
- [ ] `tests/unit/models/test_report_cache.py` -- covers REPT-08
- [ ] `tests/unit/test_report_routes.py` -- covers REPT-07 (history tab)
- [ ] `tests/unit/test_jobs_manifest.py` -- covers REPT-06 (manifest entries)
- [ ] Mock fixtures for Graph bulk API responses (userRegistrationDetails, users with licenses, signIn logs)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Existing `@auth_required` decorator on all routes |
| V3 Session Management | no | Existing session middleware handles this |
| V4 Access Control | yes | `@require_role("admin")` on all report routes + `admin_or_portal_required` on job endpoints |
| V5 Input Validation | yes | Date range inputs validated (ISO format, reasonable range); `_csv_safe()` for CSV injection prevention |
| V6 Cryptography | no | No new secrets; existing Graph/Genesys tokens managed by base services |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CSV injection via report data | Tampering | `_csv_safe()` prefixes dangerous characters with apostrophe (Phase 7 pattern) |
| Date range injection in Graph filter | Tampering | Validate date inputs as ISO 8601 format before embedding in OData filter |
| Unauthorized report access | Elevation of Privilege | `@require_role("admin")` on all report routes; portal auth on job endpoints |
| Cache poisoning via direct DB write | Tampering | Report cache written only by sync jobs (not user input); no user-writable path to report_cache table |
| API token exposure in logs | Information Disclosure | Existing `_make_request` pattern never logs tokens; only logs URL and status |

## Sources

### Primary (HIGH confidence)
- Microsoft Graph API: List users with signInActivity -- [learn.microsoft.com/graph/api/user-list](https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0) -- pagination max 500 with signInActivity, @odata.nextLink pattern
- Microsoft Graph API: userRegistrationDetails -- [learn.microsoft.com/graph/api/authenticationmethodsroot-list-userregistrationdetails](https://learn.microsoft.com/en-us/graph/api/authenticationmethodsroot-list-userregistrationdetails?view=graph-rest-1.0) -- bulk MFA status, isMfaRegistered field, AuditLog.Read.All permission
- Microsoft Graph API: Authentication methods usage reports overview -- [learn.microsoft.com/graph/api/resources/authenticationmethods-usage-insights-overview](https://learn.microsoft.com/en-us/graph/api/resources/authenticationmethods-usage-insights-overview?view=graph-rest-1.0)
- Microsoft Graph API: List signIns -- [learn.microsoft.com/graph/api/signin-list](https://learn.microsoft.com/en-us/graph/api/signin-list?view=graph-rest-1.0) -- date range filtering, AuditLog.Read.All permission
- Genesys Cloud: User Status Observations -- [developer.genesys.cloud](https://developer.genesys.cloud/analyticsdatamanagement/analytics/observation/user-query) -- bulk presence query

### Secondary (MEDIUM confidence)
- Codebase verification: `app/services/graph_service.py`, `app/services/genesys_service.py`, `app/blueprints/admin/jobs.py`, `app/models/external_service.py`, `app/utils/pagination.py`, `app/services/sku_catalog_cache.py` -- all existing patterns verified by reading source

### Tertiary (LOW confidence)
- Genesys search expand with `presence` parameter for bulk queries -- community forum references suggest it may work but official docs are ambiguous on real-time presence in search results

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new dependencies, all existing patterns verified
- Architecture: HIGH - extends proven patterns (jobs, caching, HTMX tabs, CSV export)
- Graph API patterns: HIGH - verified against official Microsoft docs
- Genesys presence approach: MEDIUM - bulk presence API path needs runtime validation
- Pitfalls: HIGH - documented from official API limitations and license requirements

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (stable -- all APIs are GA except signInActivity on beta)
