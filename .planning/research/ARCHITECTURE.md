# Architecture Patterns

**Domain:** IT Operations Platform — v4.0 feature integration
**Researched:** 2026-05-18

## Recommended Architecture

All four v4.0 features integrate into the existing Flask/PostgreSQL/HTMX architecture with minimal new abstractions. The key insight: the codebase already has the patterns needed (DI container, ReportCache model, report sync service, tab-based UI, SkuCatalogCache). v4.0 is mostly about wiring new data through existing plumbing.

### High-Level Integration Map

```
Feature                  Existing Component(s) Modified    New Component(s)
─────────────────────────────────────────────────────────────────────────────
SKU Tooltips             _m365_section.html,              (template + CSS only)
                         _build_m365_section_data()
                         SkuCatalogCache.get_sku_name()

ER Diagrams              admin blueprint                   scripts/generate_erd.py
                                                           admin/schema route
                                                           admin/partials/_schema.html

Multi-stage Docker       Dockerfile                        (Dockerfile rewrite only)

Exchange Reports         GraphService (new methods)        sync methods in ReportSyncService
                         reports.py (new tab handler)      admin/partials/_report_exchange.html
                         ReportCache (data only)

Teams Reports            GraphService (new methods)        sync methods in ReportSyncService
                         reports.py (new tab handler)      admin/partials/_report_teams.html
                         ReportCache (data only)

SharePoint/OD Reports    GraphService (new methods)        sync methods in ReportSyncService
                         reports.py (new tab handler)      admin/partials/_report_storage.html
                         ReportCache (data only)
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `SkuCatalogCache` (existing) | GUID-to-name resolution, stores `description` field from Graph | `ExternalServiceData` model, `GraphService` |
| `_m365_section.html` (modify) | Display license badges with tooltip showing friendly description | Template data from `_build_m365_section_data()` |
| `GraphService` (extend) | New bulk report methods for Exchange/Teams/SharePoint CSV endpoints | Graph API v1.0 `/reports/*` endpoints |
| `ReportSyncService` (extend) | New sync methods: `sync_exchange_data()`, `sync_teams_data()`, `sync_storage_data()` | `GraphService`, `ReportCache` |
| `reports.py` (extend) | New tab handlers and CSV export routes for Exchange, Teams, Storage | `ReportCache`, templates |
| `scripts/generate_erd.py` (new) | CLI tool to generate ER diagram from SQLAlchemy metadata | `db.metadata`, graphviz/mermaid output |
| `admin/schema` route (new) | Admin page rendering live ER diagram | `generate_erd.py` or inline metadata inspection |
| `Dockerfile` (rewrite) | Multi-stage build: builder + runtime stages | `requirements.txt`, system deps |

### Data Flow

#### SKU Tooltips (template-only change)

```
SkuCatalogCache already stores:
  ExternalServiceData.name = skuPartNumber (e.g., "ENTERPRISEPACK")
  ExternalServiceData.description = displayName (e.g., "Office 365 E3")
  ExternalServiceData.raw_data = full SKU JSON

Current flow:
  _build_m365_section_data() -> sku_catalog.get_sku_name(sku_id) -> returns `name` field
  Template shows: lic.displayName (which equals skuPartNumber or GUID)

Enhanced flow:
  _build_m365_section_data() -> add sku_catalog.get_sku_description(sku_id) -> returns `description` field
  License dict gains "tooltip" key with the human-friendly description
  Template: title="{{ lic.get('tooltip', lic.get('skuId')) }}" on badge span

Key detail: The data is ALREADY in the database. SkuCatalogCache stores `description`
from Graph's `displayName` field. We just need a `get_sku_description()` method
(mirrors `get_sku_name()`) and thread it into the template data dict.
```

#### ER Diagram Generation

```
Option A (Recommended): CLI script + admin page

  CLI: python scripts/generate_erd.py --format mermaid --output docs/erd.md
       python scripts/generate_erd.py --format png --output docs/erd.png

  Approach: Use SQLAlchemy's `db.metadata` to introspect all models.
  Walk metadata.tables, extract columns, foreign keys, build diagram.

  For Mermaid output (no graphviz dependency):
    Iterate db.metadata.sorted_tables
    For each table: emit entity with columns and types
    For each foreign_key: emit relationship line

  Admin page: /admin/schema renders Mermaid diagram using client-side
  mermaid.js (CDN or vendored). No server-side graphviz needed.
  Mermaid renders in-browser — fits HTMX/Tailwind patterns perfectly.

Option B (Rejected): eralchemy2 library
  DEPRECATED as of May 2024. Requires graphviz system dependency.
  Would need graphviz in Docker image (adds ~50MB, counterproductive
  alongside multi-stage Docker optimization goal).
```

#### Multi-Stage Docker Build

```
Current single-stage:
  python:3.12-slim -> apt-get (ODBC + curl) -> pip install -> COPY .

Multi-stage:
  Stage 1 "builder": python:3.12-slim
    - Install build-time system deps (gcc, python3-dev, unixodbc-dev, gnupg2)
    - Install ODBC driver 18
    - pip install --user (or to /install) all Python deps
    - Build artifacts: /usr/local/lib/python3.12/, ODBC driver libs

  Stage 2 "runtime": python:3.12-slim
    - Install runtime-only system deps (curl, libodbc2, postgresql-client)
    - COPY --from=builder /usr/local/lib/python3.12/site-packages
    - COPY --from=builder /opt/microsoft/msodbcsql18 (ODBC driver)
    - COPY --from=builder /etc/odbcinst.ini
    - COPY . .
    - Same USER, HEALTHCHECK, ENTRYPOINT as before

Impact:
  - gnupg2, gcc, python3-dev, build headers NOT in final image
  - Estimated savings: 100-200MB (from ~500MB to ~300MB range)
  - Dev workflow unchanged: same docker-compose, same entrypoint
  - Build time slightly longer (two stages), but cache-friendly
    since requirements.txt changes trigger only builder rebuild
```

#### Advanced M365 Reports (Exchange, Teams, SharePoint/OneDrive)

```
All three report types follow the IDENTICAL pattern to existing license/security reports:

1. GraphService gets new methods that call Graph v1.0 usage report endpoints
   - These endpoints return CSV via 302 redirect (not JSON!)
   - GraphService methods must follow redirect, parse CSV, return list of dicts
   - Permission required: Reports.Read.All (application permission)

2. ReportSyncService gets new sync methods (one per report type)
   - Calls GraphService, transforms data, stores via ReportCache.store()
   - Each uses appropriate TTL (4h for Exchange/storage, 1h for Teams activity)

3. Reports blueprint gets new tab handlers + CSV export routes
   - Follows exact pattern of _render_licenses_tab / _render_security_tab
   - New HTMX partials for each tab

4. SandCastle job scheduler gets new scheduled jobs
   - report_exchange_sync, report_teams_sync, report_storage_sync

Data flow per report type:

  Graph API (CSV) -> GraphService.get_*_report() [parse CSV to dicts]
                  -> ReportSyncService.sync_*_data() [aggregate KPIs]
                  -> ReportCache.store(report_type, cache_key, data, ttl)
                  -> reports.py _render_*_tab() [read from ReportCache]
                  -> _report_*.html partial [KPI cards + data table]
```

## Graph API Report Endpoints (Verified)

All require `Reports.Read.All` application permission. All return CSV via 302 redirect.
Period options: D7, D30, D90, D180.

### Exchange Mailbox

| Endpoint | Data Returned |
|----------|--------------|
| `GET /reports/getMailboxUsageDetail(period='{period}')` | Per-user: UPN, item count, storage used, quotas, deleted items, has archive, last activity |
| `GET /reports/getMailboxUsageMailboxCounts(period='{period}')` | Aggregate counts by mailbox type over time |
| `GET /reports/getMailboxUsageQuotaStatusMailboxCounts(period='{period}')` | Quota status distribution (under limit, warning, send prohibited) |
| `GET /reports/getMailboxUsageStorage(period='{period}')` | Aggregate storage trend over time |

### Teams

| Endpoint | Data Returned |
|----------|--------------|
| `GET /reports/getTeamsUserActivityUserDetail(period='{period}')` | Per-user: chat messages, calls, meetings, audio/video duration, last activity |
| `GET /reports/getTeamsUserActivityCounts(period='{period}')` | Daily activity counts (messages, calls, meetings) |
| `GET /reports/getTeamsDeviceUsageUserDetail(period='{period}')` | Per-user device usage: Windows, Mac, Web, iOS, Android |

### SharePoint / OneDrive

| Endpoint | Data Returned |
|----------|--------------|
| `GET /reports/getSharePointSiteUsageDetail(period='{period}')` | Per-site: URL, storage used, file count, page views, last activity |
| `GET /reports/getSharePointSiteUsageStorage(period='{period}')` | Aggregate storage trend over time |
| `GET /reports/getOneDriveUsageAccountDetail(period='{period}')` | Per-user: storage used, file count, last activity |
| `GET /reports/getOneDriveUsageStorage(period='{period}')` | Aggregate storage trend |

### Critical Implementation Detail: CSV Response Handling

Graph report endpoints do NOT return JSON. They return a 302 redirect to a pre-authenticated CSV download URL. The existing `_make_request` in `BaseAPIService` follows redirects by default (requests library behavior), but the response content type will be `application/octet-stream` (CSV bytes), not JSON.

New GraphService methods must:
1. Make GET request (redirect auto-followed by requests)
2. Decode response content as UTF-8
3. Parse CSV using Python's `csv.DictReader`
4. Return list of dicts

```python
def _fetch_report_csv(self, endpoint: str, period: str = "D7") -> List[Dict[str, str]]:
    """Fetch a Graph usage report CSV and return as list of dicts."""
    token = self.get_access_token()
    if not token:
        return []
    url = f"https://graph.microsoft.com/v1.0/reports/{endpoint}(period='{period}')"
    response = self._make_request("GET", url, token)
    # Response is CSV bytes after following 302 redirect
    import csv, io
    reader = csv.DictReader(io.StringIO(response.text))
    return list(reader)
```

### Tenant Privacy Setting: User Identity Concealment

By default, M365 usage reports conceal user identity (UPNs replaced with hashes). To show actual usernames, the tenant admin must disable the privacy setting via M365 Admin Center > Settings > Org Settings > Reports, or via Graph API:

```
PATCH /v1.0/admin/reportSettings
{ "displayConcealedNames": false }
```

This requires `ReportSettings.ReadWrite.All` permission. Document this prerequisite clearly -- without it, Exchange/Teams/SharePoint reports will show anonymized user IDs instead of real names.

## Patterns to Follow

### Pattern 1: Report Tab Extension (follow existing license/security pattern exactly)

**What:** Add new tabs to the existing reports page for Exchange, Teams, and Storage.
**When:** All three new report types.
**Example:**

```python
# In reports.py - extend the tab_handlers dict
tab_handlers = {
    "licenses": _render_licenses_tab,
    "security": _render_security_tab,
    "genesys": _render_genesys_tab,
    "exchange": _render_exchange_tab,      # NEW
    "teams": _render_teams_tab,            # NEW
    "storage": _render_storage_tab,        # NEW
    "history": _render_history_tab,
}
```

### Pattern 2: ReportCache Store/Retrieve (existing pattern)

**What:** Use ReportCache.store() for pre-computed aggregations, ReportCache.get_cached() for rendering.
**When:** All report data.
**Example:**

```python
# Store pattern (in ReportSyncService)
ReportCache.store("exchange_mailbox", "per_user", per_user_data, ttl_hours=4)
ReportCache.store("exchange_mailbox", "totals", totals_data, ttl_hours=4)

# Retrieve pattern (in reports.py tab handler)
totals_cache = ReportCache.get_cached("exchange_mailbox", "totals")
detail_cache = ReportCache.get_cached("exchange_mailbox", "per_user")
```

### Pattern 3: Permission Degradation (existing D-06 pattern)

**What:** GraphService methods return `{"error": "permission_missing", "permission": "..."}` on 403.
**When:** Reports.Read.All not granted.
**Example:** Template renders inline warning banner instead of crashing.

### Pattern 4: Mermaid ER Diagram from SQLAlchemy Metadata

**What:** Walk `db.metadata.sorted_tables` to generate Mermaid syntax, render client-side.
**When:** Schema visualization feature.
**Example:**

```python
def generate_mermaid_erd(metadata) -> str:
    lines = ["erDiagram"]
    for table in metadata.sorted_tables:
        for col in table.columns:
            col_type = str(col.type)[:20]
            pk = "PK" if col.primary_key else ""
            fk = "FK" if col.foreign_keys else ""
            key = pk or fk
            lines.append(f'    {table.name} {{ {col_type} {col.name} {key} }}')
        for fk in table.foreign_keys:
            parent = fk.column.table.name
            lines.append(f'    {parent} ||--o{{ {table.name} : "has"')
    return "\n".join(lines)
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Adding Graphviz as a System Dependency

**What:** Installing graphviz in the Docker image for ER diagram generation.
**Why bad:** Adds ~50MB to image, directly conflicts with Docker optimization goal. Requires system package in Dockerfile.
**Instead:** Use Mermaid.js for client-side rendering. Generate Mermaid syntax server-side from SQLAlchemy metadata. No system dependencies needed. Mermaid renders beautifully in modern browsers and can be exported as SVG/PNG from the browser.

### Anti-Pattern 2: Creating New Models for Report Data

**What:** Adding ExchangeReport, TeamsReport, SharePointReport models with dedicated tables.
**Why bad:** ReportCache already provides a generic, proven storage mechanism with TTL and staleness detection. New models would duplicate this infrastructure.
**Instead:** Use ReportCache.store() with distinct report_type keys ("exchange_mailbox", "teams_activity", "storage_usage"). The JSON column handles any data shape.

### Anti-Pattern 3: Calling Graph Report Endpoints Live on Tab Load

**What:** Fetching Exchange/Teams/SharePoint data on every tab render.
**Why bad:** Graph report endpoints are slow (CSV download + parse), and have rate limits. The existing license/security tabs use cached data for exactly this reason.
**Instead:** Always go through ReportSyncService -> ReportCache. Sync on schedule (every 4h). Tab renders from cache. This is the established pattern.

### Anti-Pattern 4: Separate Docker Build for Dev vs Prod

**What:** Creating two Dockerfiles or complex build args to differentiate dev/prod builds.
**Why bad:** Drift between dev and prod images. Multi-stage naturally handles this: the builder stage is the "dev-like" environment, the runtime stage is prod.
**Instead:** Single multi-stage Dockerfile. Dev uses docker-compose which can target the builder stage if needed (via `--target builder`), prod uses the default final stage.

## New Graph API Permission Requirements

| Permission | Type | Required For | Notes |
|-----------|------|-------------|-------|
| `Reports.Read.All` | Application | Exchange, Teams, SharePoint/OneDrive reports | **Critical: requires admin consent** |
| `ReportSettings.ReadWrite.All` | Application | Disable user identity concealment (optional) | Needed to see real UPNs in reports |

The existing app registration already has: `User.Read.All`, `Organization.Read.All`, `AuditLog.Read.All`, `UserAuthenticationMethod.Read.All`, `Directory.Read.All`. Adding `Reports.Read.All` is the only mandatory new permission.

## Scalability Considerations

| Concern | At current scale (~200 users) | At 1K users | At 10K users |
|---------|-------------------------------|-------------|-------------|
| Graph CSV report size | Small CSV, fast parse | Medium CSV (~100KB), still fast | Large CSV (~1MB+), may need streaming parse |
| ReportCache JSON size | Negligible | 100KB-1MB per report type | Consider pagination in cache or summary-only storage |
| ER diagram complexity | ~20 tables, renders instantly | Same (schema doesn't scale with users) | Same |
| Docker image size | ~300MB target | Same | Same |

For the current scale of ~200 users and ~20 database tables, none of these features have scalability concerns. The architecture choices (cached reports, client-side Mermaid rendering, multi-stage Docker) are appropriate for 10x growth without changes.

## Build Order (Dependency-Driven)

```
Phase ordering based on dependencies:

1. SKU Tooltips — ZERO dependencies on other features
   - Only modifies template + one service method
   - Quick win, immediate UX value

2. Multi-Stage Docker — ZERO dependencies on other features
   - DevOps improvement, independent of app code
   - Do early to establish smaller base image for all subsequent deploys

3. ER Diagrams — ZERO dependencies on other features
   - Developer tooling, independent
   - Lower priority than user-facing features

4. Exchange Reports — Requires Reports.Read.All permission granted first
   - Build the CSV parsing infrastructure in GraphService
   - First report type establishes the pattern

5. Teams Reports — Depends on Exchange (reuses CSV parsing pattern)
   - Second report type, faster to build (pattern established)

6. SharePoint/OneDrive Reports — Depends on Exchange (reuses CSV parsing pattern)
   - Third report type, fastest (pure pattern replication)

Permission dependency: Steps 4-6 all require Reports.Read.All to be
granted on the Azure AD app registration BEFORE development begins.
Start the consent request in parallel with steps 1-3.
```

## Sources

- [Microsoft Graph Usage Reports API](https://learn.microsoft.com/en-us/graph/api/resources/report?view=graph-rest-1.0) -- HIGH confidence
- [Graph Mailbox Usage Detail](https://learn.microsoft.com/en-us/graph/api/reportroot-getmailboxusagedetail?view=graph-rest-1.0) -- HIGH confidence
- [Graph Teams User Activity Detail](https://learn.microsoft.com/en-us/graph/api/reportroot-getteamsuseractivityuserdetail?view=graph-rest-1.0) -- HIGH confidence
- [Graph Reports Authorization](https://learn.microsoft.com/en-us/graph/reportroot-authorization) -- HIGH confidence
- [eralchemy2 (DEPRECATED)](https://github.com/maurerle/eralchemy2) -- HIGH confidence (verified deprecated)
- [Docker Multi-Stage Python Builds](https://testdriven.io/blog/docker-best-practices/) -- MEDIUM confidence
- Existing codebase analysis (SkuCatalogCache, ReportSyncService, GraphService, reports.py, Dockerfile) -- HIGH confidence
