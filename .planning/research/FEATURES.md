# Feature Landscape

**Domain:** IT Operations Platform — UX Polish, DevOps Optimization, Advanced M365 Reporting
**Researched:** 2026-05-18

## Table Stakes

Features users expect once the capability category exists. Missing = product feels incomplete.

### 1. SKU Friendly-Name Tooltips

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Hover tooltip showing human-readable license description | Users already see `displayName` on profile badges — but cryptic SKU IDs like `ENTERPRISEPACK` still appear in `title` attribute. IT staff expect to see "Office 365 E3" not a GUID. | Low | Microsoft publishes an official CSV mapping GUID to Product_Display_Name at a stable URL. The existing `SkuCatalogCache` already resolves GUID to name. |
| Service plan breakdown in tooltip | Admins want to know what's *inside* a SKU (Exchange Online, SharePoint, Teams) without leaving the page | Low-Med | The SKU CSV includes `Service_Plans_Included_Friendly_Names`. Can be parsed during cache refresh and stored alongside the SKU entry. |
| Tooltip accessible via keyboard (focus, not just hover) | Accessibility table stakes — screen readers and keyboard-only users need tooltip content | Low | Use `aria-describedby` with a hidden element or Tailwind/CSS tooltip that triggers on `:focus` as well as `:hover`. |

**User behavior:** IT staff hover over a license badge to confirm what a user has. They expect instant display (no API call), readable names, and ideally a list of included service plans. Tooltips should dismiss on mouseout/blur.

**Dependency:** Existing `SkuCatalogCache` service with 24h TTL refresh. Current template at `_m365_section.html` line 108 already sets `title="{{ lic.get('skuId') }}"` — this is the exact insertion point.

### 2. Docker Multi-Stage Build Optimization

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Separate build stage from runtime stage | Standard practice for production Python containers. Current single-stage build includes build tools, pip cache, and ODBC driver install artifacts in final image. | Low-Med | Current Dockerfile is single-stage `python:3.12-slim` with inline ODBC driver install. Multi-stage separates compilation deps (gnupg2, curl for key fetch) from runtime. |
| Use `python:3.12-slim` for runtime, heavier base for build | Expected pattern — 80-90% size reduction is typical for Python apps with C extensions (psycopg2, pyodbc) | Low-Med | The ODBC driver install is the tricky part — `msodbcsql18` runtime libs must remain, but `gnupg2` and signing keys are build-only. |
| `.dockerignore` for venv, `.git`, tests, docs | Prevents bloating build context | Low | Check if `.dockerignore` exists; if not, create one. |
| Non-root user preserved | Already implemented (user `app`, UID 10001) — must survive multi-stage | Low | Copy user creation to final stage or use `--from=build`. |

**User behavior:** DevOps concern, not end-user facing. Developer expects `docker build` to produce a small, secure image. Target: under 300MB (from likely 500MB+ currently). Faster pulls on SandCastle deploys.

**Dependency:** Existing `Dockerfile` and `docker-compose.sandcastle.yml`. Must preserve ODBC driver for pyodbc (Azure SQL warehouse), healthcheck, entrypoint.

### 3. Exchange Mailbox Reporting

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-user mailbox size and item count | Core mailbox analytics — IT needs to know who's consuming storage | Med | Graph `getMailboxUsageDetail(period='D30')` returns: Storage Used (Byte), Item Count, quota thresholds, last activity date, archive status. Returns CSV by default, JSON via beta. |
| Mailbox quota status overview | Users approaching quota limits need proactive management | Med | Graph `getMailboxUsageQuotaStatusMailboxCounts` gives counts per quota tier (under limit, warning, send restricted, send/receive restricted). |
| Email activity metrics (send/receive counts) | IT wants to identify inactive or high-volume mailboxes | Med | Graph `getEmailActivityUserDetail(period='D30')` returns send/receive/read counts per user per period. |
| Storage trend over time | Shows growth trajectory for capacity planning | Med-High | Graph `getMailboxUsageStorage` gives org-level storage trend. Per-user trends require storing snapshots over multiple sync cycles. |
| Tabbed integration with existing reports | Existing reports page has licenses/security/genesys/history tabs — Exchange must follow the same pattern | Low | Extend `_render_tab` dispatch in `reports.py`, add new partial template. |

**User behavior:** Admin navigates to Reports > Exchange tab. Sees KPI cards (total mailboxes, storage used, users near quota). Below: sortable table of users by mailbox size. Clicks column headers to sort. Exports to CSV.

**Dependency:** Requires `Reports.Read.All` Graph permission (tenant admin consent). Existing `ReportSyncService` pattern for caching. Existing `ReportCache` model for storage. Must add new sync job to SandCastle scheduler.

### 4. Teams Usage Reporting

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| User activity summary (messages, calls, meetings) | Core Teams analytics — who's active, who's dormant | Med | Graph `getTeamsUserActivityUserDetail(period='D30')` returns per-user: team chat messages, private chat messages, calls, meetings, audio/video/screen share duration. |
| Team-level activity (per team, not just per user) | Admins want to see which teams are active vs abandoned | Med | Graph `getTeamsTeamActivityDetail` returns per-team meeting and message counts. |
| Device usage breakdown | Useful for IT planning (desktop vs mobile vs web) | Low-Med | Graph `getTeamsDeviceUsageUserDetail` returns per-user device types. |
| Call records and quality (basic) | IT support needs call history for troubleshooting | High | Graph `callRecords` API requires `CallRecords.Read.All` permission (separate from Reports). Basic records available; detailed quality metrics (jitter, packet loss) require Call Quality Dashboard, NOT directly available via Graph API. |
| KPI cards and table layout matching existing reports | Consistency with license/security tab patterns | Low | Follow established pattern. |

**User behavior:** Admin views Reports > Teams tab. KPI cards show active users, total messages, total calls/meetings. Table shows per-user breakdown sortable by activity. Time period selector (7d/30d/90d/180d) matching Graph API periods.

**Dependency:** `Reports.Read.All` for usage reports. `CallRecords.Read.All` for call records (separate permission, separate consent). Existing report infrastructure.

### 5. SharePoint/OneDrive Storage Reporting

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-site storage usage and file counts | Core storage management — identify sites consuming most storage | Med | Graph `getSharePointSiteUsageDetail` returns per-site: storage used, file count, active file count, page views, last activity. |
| OneDrive per-account storage | Individual user storage consumption | Med | Graph `getOneDriveUsageAccountDetail` returns per-account: storage used, file count, active file count, last activity. |
| Organization-level storage trends | Capacity planning for SharePoint and OneDrive | Med | Graph `getSharePointSiteUsageStorage` and `getOneDriveUsageStorage` give org-level trends. |
| File activity summary (views, edits, shares) | Understand collaboration patterns | Low-Med | Graph `getSharePointActivityUserDetail` and `getOneDriveActivityUserDetail` return per-user file interaction counts. |
| Site count and active site trends | Governance — how many sites exist, how many are active | Low | Graph `getSharePointSiteUsageSiteCounts` gives active/total trends. |

**User behavior:** Admin views Reports > SharePoint tab. KPI cards: total storage used, total sites, top consumers. Two sub-sections: SharePoint Sites (sorted by storage) and OneDrive Accounts (sorted by storage). Size values displayed in human-readable format (GB/TB). CSV export.

**Dependency:** `Reports.Read.All` Graph permission. Same infrastructure as Exchange reporting.

### 6. Schema Visualization (ER Diagrams)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Auto-generated ER diagram from live database metadata | Developer/admin tool for understanding the 20+ table schema without reading SQL files | Med | Two approaches: (A) server-side generation via `eralchemy2` (SVG/PNG output), or (B) server generates Mermaid ER syntax from `pg_catalog`, client renders via Mermaid.js. |
| Table names, columns, types, relationships | Minimum viable schema visualization | Low-Med | PostgreSQL `information_schema` or `pg_catalog` provides all metadata. Foreign key relationships discoverable via `pg_constraint`. |
| Interactive (zoom, pan, click-to-inspect) | Static images become unreadable at 20+ tables | Med | Mermaid.js renders SVG which supports native browser zoom. For click-to-inspect, need custom JS overlay or use a library like `svg-pan-zoom`. |
| Refresh on demand (not stale) | Schema may change with Alembic migrations | Low | Generate on request from live database metadata, not cached. |

**User behavior:** Admin navigates to Admin > Database > Schema tab (or dedicated page). Sees full ER diagram of all tables with relationships. Can zoom/pan to navigate. Optionally clicks a table to see column details. Primarily a developer/admin reference tool, used infrequently.

**Dependency:** PostgreSQL metadata queries. Either `eralchemy2` + Graphviz system dependency (heavier, adds to Docker image) or Mermaid.js (client-side, no server dependency). Mermaid.js preferred to avoid bloating Docker image.

## Differentiators

Features that set the product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| SKU tooltip with service plan decomposition | Most admin tools show SKU name only; showing included plans (Exchange Online Plan 2, Teams, etc.) saves a trip to M365 admin center | Low-Med | Parse `Service_Plans_Included_Friendly_Names` from Microsoft CSV during SKU cache refresh |
| Cross-report correlation (mailbox size vs license cost) | Identify users with expensive licenses but no mailbox activity — license optimization | High | Requires joining license data with Exchange activity data; builds on existing license reporting |
| Forwarding rule detection in Exchange reporting | Security value — unauthorized forwarding rules are a common exfiltration vector | High | Requires `MailboxSettings.Read` permission (separate from Reports.Read.All); uses `GET /users/{id}/mailboxSettings` per-user |
| Teams call quality integration | Most internal tools skip call quality; providing even basic metrics differentiates | High | Requires `CallRecords.Read.All`, webhook subscription for real-time records, and local aggregation |
| Schema visualization with Alembic migration history overlay | Show which migrations changed which tables — unique dev tool | High | Requires parsing Alembic version history and correlating with schema changes |
| Docker layer caching optimization with BuildKit | Beyond multi-stage — mount caches for pip, use `--mount=type=cache` for faster rebuilds | Low | BuildKit feature, no additional deps, speeds up CI builds significantly |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-time call quality dashboard | Requires persistent webhook subscriptions, significant infrastructure (event processing, storage), and `CallRecords.Read.All` consent — disproportionate effort for 4-5 users | Link to Microsoft Call Quality Dashboard (CQD) from Teams report tab |
| Mail flow rules / transport rules reporting | Requires Exchange admin permissions beyond Graph API scope; mail flow data not available via standard Graph reporting endpoints | Note limitation in UI; direct users to Exchange Admin Center |
| Interactive schema editor (modify tables from UI) | Dangerous — schema changes must go through Alembic migrations for safety | Read-only visualization only |
| SharePoint site-level permission reporting | Requires `Sites.Read.All` and per-site enumeration — expensive, slow, and privacy-sensitive | Show storage/activity only, not permissions |
| Full PowerBI-style analytics embedding | Over-engineered for team size; adds complexity without proportional value | Keep reports as server-rendered HTML tables with KPI cards and CSV export |
| Tooltip with live Graph API call on hover | Adds latency, API rate limit risk, and poor UX (loading spinner on hover) | Pre-cache all SKU data in `SkuCatalogCache` (already done) |
| Per-user mail content search or preview | Major privacy/compliance concern; not appropriate for an IT ops tool | Show metadata only (counts, sizes, dates) |

## Feature Dependencies

```
SkuCatalogCache (exists) --> SKU Friendly-Name Tooltips
  SKU Tooltips --> Service Plan Decomposition (differentiator)

Reports.Read.All permission (new) --> Exchange Mailbox Reporting
Reports.Read.All permission (new) --> Teams Usage Reporting
Reports.Read.All permission (new) --> SharePoint/OneDrive Reporting

ReportSyncService (exists) --> Exchange sync job
ReportSyncService (exists) --> Teams sync job
ReportSyncService (exists) --> SharePoint sync job
ReportCache model (exists) --> All new report storage

Existing reports tab UI (exists) --> New report tab partials

PostgreSQL metadata access (exists) --> Schema Visualization
Mermaid.js (new client dep) --> Interactive ER diagrams

Dockerfile (exists) --> Multi-stage Docker build
```

## MVP Recommendation

Prioritize:
1. **SKU friendly-name tooltips** — lowest effort, immediate UX polish, zero new permissions needed, builds on existing `SkuCatalogCache`
2. **Docker multi-stage build** — DevOps hygiene, no external dependencies, measurable improvement (target 50%+ size reduction)
3. **Schema visualization** — self-contained developer tool, no external API permissions, moderate complexity
4. **Exchange mailbox reporting** — highest-value new report (mailbox size is the most-asked-about metric), establishes pattern for Teams and SharePoint
5. **Teams usage reporting** — follows Exchange pattern, same permission requirement
6. **SharePoint/OneDrive reporting** — follows Exchange pattern, same permission, lowest individual value of the three

Defer:
- **Call quality metrics (detailed):** Requires separate `CallRecords.Read.All` permission, webhook infrastructure, and significant complexity for minimal value at this team size. Provide basic call/meeting counts from `Reports.Read.All` instead.
- **Forwarding rule detection:** Requires per-user `MailboxSettings.Read` calls (N+1 API pattern), separate permission consent. Flag as future differentiator.
- **Cross-report correlation:** Valuable but depends on all three report types being built first. Natural Phase 2 enhancement.

## Graph API Permission Requirements

All three advanced reporting features share a single permission gate:

| Permission | Type | Reports Unlocked | Consent Required |
|------------|------|-----------------|------------------|
| `Reports.Read.All` | Application | Exchange, Teams, SharePoint, OneDrive, Email Activity, M365 Groups | Tenant admin consent |
| `CallRecords.Read.All` | Application | Call records with quality data | Tenant admin consent (defer) |
| `MailboxSettings.Read` | Application | Forwarding rules per user | Tenant admin consent (defer) |

**Critical:** `Reports.Read.All` is the single gate for all three reporting workstreams. Request this permission once; it unlocks Exchange, Teams, and SharePoint reports. The existing Graph app registration already has `User.Read.All`, `Directory.Read.All`, etc. — adding `Reports.Read.All` is an incremental admin consent step, not a new app registration.

**Data freshness:** Graph reporting endpoints are ~48 hours behind real-time. This is a Microsoft limitation, not a bug. Document this clearly in the UI.

## Complexity Summary

| Feature | Complexity | New Dependencies | New Permissions |
|---------|------------|------------------|-----------------|
| SKU Tooltips | Low | None | None |
| Docker Multi-Stage | Low-Med | None | None |
| Schema Visualization | Med | Mermaid.js (CDN) | None |
| Exchange Reporting | Med | None | Reports.Read.All |
| Teams Reporting | Med | None | Reports.Read.All (shared) |
| SharePoint/OneDrive | Med | None | Reports.Read.All (shared) |

## Sources

- [Microsoft Graph reportRoot API reference](https://learn.microsoft.com/en-us/graph/api/resources/reportroot?view=graph-rest-1.0) — HIGH confidence
- [getMailboxUsageDetail endpoint](https://learn.microsoft.com/en-us/graph/api/reportroot-getmailboxusagedetail?view=graph-rest-1.0) — HIGH confidence
- [Graph reporting authorization](https://learn.microsoft.com/en-us/graph/reportroot-authorization) — HIGH confidence
- [M365 SKU product names and service plan identifiers](https://learn.microsoft.com/en-us/entra/identity/users/licensing-service-plan-reference) — HIGH confidence
- [eralchemy2 PyPI](https://pypi.org/project/eralchemy2/) — MEDIUM confidence
- [Mermaid.js ER diagram syntax](https://mermaid.js.org/syntax/entityRelationshipDiagram.html) — HIGH confidence
- [mermerd - Mermaid ERD from existing tables](https://github.com/KarnerTh/mermerd) — MEDIUM confidence
- [Docker multi-stage builds for Python](https://medium.com/ai-innovation/strategies-for-reducing-docker-image-size-with-python-flask-feef86a63349) — MEDIUM confidence
- [Graph call records API overview](https://learn.microsoft.com/en-us/graph/api/resources/callrecords-api-overview?view=graph-rest-1.0) — HIGH confidence
- [OneDrive usage account detail](https://learn.microsoft.com/en-us/graph/api/reportroot-getonedriveusageaccountdetail?view=graph-rest-1.0) — HIGH confidence
- [SharePoint site usage storage](https://learn.microsoft.com/en-us/graph/api/reportroot-getsharepointsiteusagestorage?view=graph-rest-1.0) — HIGH confidence
- [Reports.Read.All permission reference](https://graphpermissions.merill.net/permission/Reports.Read.All) — MEDIUM confidence
