# Domain Pitfalls

**Domain:** Adding SKU tooltips, ER diagrams, Docker optimization, and advanced M365 reporting to an existing Flask/PostgreSQL/HTMX IT operations platform
**Researched:** 2026-05-18

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Graph Usage Reports Return CSV with 302 Redirects, Not JSON

**What goes wrong:** The Exchange, Teams, and SharePoint usage report endpoints (`getEmailActivityUserDetail`, `getTeamsUserActivityUserDetail`, `getSharePointSiteUsageDetail`, `getOneDriveUsageAccountDetail`) return a `302 Found` redirect to a pre-authenticated download URL that serves CSV data. This is fundamentally different from every other Graph endpoint WhoDis currently uses, which all return JSON. Code that uses `_make_request()` and `_handle_response()` (which calls `response.json()`) will break immediately.

**Why it happens:** The existing `BaseAPITokenService._make_request()` pattern assumes JSON responses. The reports API was designed for bulk export, not real-time querying.

**Consequences:** Silent failures or crashes in the report sync pipeline. The pre-authenticated download URL is only valid for a few minutes, so retrying after a parse error may require a fresh API call.

**Prevention:**
- Add a dedicated `_make_report_request()` method to `GraphService` that follows redirects and parses CSV (or appends `?$format=application/json` to request JSON format where supported).
- The JSON format option (`$format=application/json`) is available on most v1.0 report endpoints -- use it to stay consistent with the existing codebase pattern.
- Test with both `$format=application/json` and default CSV to verify the endpoint supports JSON for each specific report type.

**Detection:** Any report sync that returns `None` or raises `JSONDecodeError` in logs.

**Phase:** Must be addressed in the first reporting phase -- this is foundational plumbing.

### Pitfall 2: Concealed Usernames in Usage Reports (Privacy Setting)

**What goes wrong:** Microsoft 365 tenants have a privacy setting (`adminReportSettings.displayConcealedNames`) that replaces actual usernames in usage reports with hashed/anonymized identifiers. When this is enabled (the default since 2022), all report data comes back with values like `FC64E1B77F0F4AC584F29F4D6E2B2E92` instead of `jsmith@example.com`. WhoDis would display meaningless hashes instead of employee names.

**Why it happens:** Microsoft changed the default to concealed in September 2022 for GDPR/privacy compliance. Tenant admins must explicitly disable concealment. This setting is invisible from the API consumer's perspective -- the data just arrives anonymized with no error.

**Consequences:** Reports look like they work but are useless. Users see hash strings instead of names. Correlating report data back to employee profiles becomes impossible.

**Prevention:**
- On first report sync, check `GET /v1.0/admin/reportSettings` to read the `displayConcealedNames` setting. Requires `ReportSettings.Read.All` permission.
- If concealed, display a clear admin banner: "Usage reports show anonymized data. A Global Administrator must disable concealed names in Microsoft 365 admin center or via Graph API."
- Do NOT programmatically change this setting without explicit admin consent -- it has org-wide privacy implications and requires `ReportSettings.ReadWrite.All` + Global Administrator role.

**Detection:** Report data contains UPN-like fields that don't match any known email patterns (long hex strings).

**Phase:** Must be validated before building any report UI. Add a pre-flight check to the first reporting phase.

### Pitfall 3: Reports.Read.All Application Permission May Not Be Sufficient

**What goes wrong:** WhoDis uses client credentials flow (application permissions, not delegated). Some report endpoints have historically had inconsistent support for application permissions. The `Reports.Read.All` application permission is required, but some newer report types or the `adminReportSettings` endpoint may require delegated permissions or additional roles.

**Why it happens:** Microsoft's permission model for reports has evolved. The newer Graph API usage reports (introduced 2024) initially only supported delegated permissions.

**Consequences:** Code works in development with delegated auth but fails silently in production with the app-only client credentials flow.

**Prevention:**
- Verify each specific report endpoint supports application permissions by testing with the existing client credentials token before building the feature.
- The core M365 usage reports (email activity, Teams activity, SharePoint usage, OneDrive usage) DO support `Reports.Read.All` as application permission in v1.0 -- this is confirmed in official docs.
- `CallRecords.Read.All` for Teams call logs ONLY supports application permissions (no delegated option) -- this is actually a positive for WhoDis's architecture.
- Document the full permission manifest in the phase plan so tenant admin consent can be obtained in a single request.

**Detection:** 403 responses from report endpoints. The existing `_permission_missing()` D-06 pattern will catch this -- extend it to cover report endpoints.

**Phase:** Permission verification should be the FIRST task in the reporting phase, before any code.

### Pitfall 4: Multi-Stage Docker Build Breaks ODBC Driver Installation

**What goes wrong:** The current Dockerfile installs Microsoft ODBC Driver 18 for Azure SQL (required for the Keystone data warehouse via pyodbc). In a multi-stage build, the build stage installs compilation dependencies and the runtime stage copies only Python packages. But ODBC drivers are system-level packages with shared libraries (`/opt/microsoft/msodbcsql18/`) and ODBC configuration files (`/etc/odbcinst.ini`). A naive `COPY --from=builder` of just the Python site-packages will miss the ODBC runtime entirely.

**Why it happens:** Python multi-stage build guides focus on pip packages and forget system-level dependencies. The ODBC driver is installed via `apt-get`, not `pip`, so it lives outside the Python ecosystem.

**Consequences:** Container builds succeed but pyodbc connections fail at runtime with `[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 18 for SQL Server'`. This only manifests when the job role compliance warehouse sync runs, which may not be tested during the Docker optimization work.

**Prevention:**
- The ODBC driver installation MUST happen in the runtime stage, not the build stage. It cannot be copied between stages.
- Structure the multi-stage build as: (1) builder stage for pip wheel compilation, (2) runtime stage that installs ODBC driver via apt + copies compiled wheels from builder.
- Test the warehouse sync endpoint after the Docker change, not just the main search flow.

**Detection:** Errors in `JobRoleWarehouseService` or any pyodbc-dependent code path. Run `docker exec <container> python -c "import pyodbc; print(pyodbc.drivers())"` to verify.

**Phase:** Docker optimization phase. Add warehouse sync to the post-build verification checklist.

## Moderate Pitfalls

### Pitfall 5: SKU Display Names Are Not Returned by subscribedSkus

**What goes wrong:** The `subscribedSkus` endpoint returns `skuPartNumber` (e.g., `ENTERPRISEPACK`) and `skuId` (GUID), but the `skuPartNumber` is a technical identifier, not a user-friendly name. The actual display name (e.g., "Office 365 E3") is not a field on the `subscribedSku` resource. The existing `SkuCatalogCache` stores `skuPartNumber` as `name` and `displayName` as `description` -- but `displayName` on `subscribedSku` may not exist or may be empty depending on the tenant.

**Why it happens:** Microsoft maintains a separate CSV mapping file for GUID-to-friendly-name translation. The Graph API itself does not reliably provide the marketing name. The `skuPartNumber` has historically been stable (it does not change with rebranding), but the friendly display name changes frequently (e.g., "Office 365 E3" became "Microsoft 365 E3").

**Consequences:** Tooltips show `ENTERPRISEPACK` instead of "Microsoft 365 E3". The current `SkuCatalogCache` already stores whatever Graph returns, but the tooltip feature needs the friendly name.

**Prevention:**
- Download and cache Microsoft's official SKU reference CSV from `https://download.microsoft.com/download/e/3/e/e3e9faf2-f28b-490a-9ada-c6089a1fc5b0/Product names and service plan identifiers for licensing.csv`.
- Use it as a fallback/enrichment layer on top of `subscribedSkus` data.
- The CSV maps `GUID`, `String_Id` (= skuPartNumber), and `Product_Display_Name`.
- Refresh the CSV monthly (Microsoft updates it periodically but not on a predictable schedule).
- Store in `external_service_data` with `data_type='sku_display_names'`.

**Detection:** SKU tooltips showing technical identifiers like `ENTERPRISEPACK` or `SPE_E3` instead of friendly names.

**Phase:** SKU tooltips phase. Must be addressed before the tooltip UI work.

### Pitfall 6: Usage Reports Data Lag of 24-72 Hours (Sometimes Longer)

**What goes wrong:** Microsoft Graph usage reports are not real-time. Data typically lags 24-48 hours behind, and community reports indicate delays of 72+ hours are not uncommon, especially for Teams activity data. Building a "live dashboard" expectation will confuse users.

**Why it happens:** Microsoft aggregates usage data in batch pipelines. The data processing has inherent latency that varies by service and tenant size.

**Consequences:** Users see stale data and think the feature is broken. Admins query "today's" Teams usage and get empty results, filing bug reports.

**Prevention:**
- Display a clear "Data as of: [date]" timestamp on every report view. The report response includes a `Report Refresh Date` field -- parse and display it.
- Set the reporting sync schedule to daily (not more frequent) -- more frequent syncs waste API calls on unchanged data.
- Default date range queries to end 2 days ago, not today.
- Document in the UI that data freshness is controlled by Microsoft, not WhoDis.

**Detection:** Reports showing empty data for recent dates. Compare `Report Refresh Date` against current date.

**Phase:** All reporting phases. The UI must communicate this from day one.

### Pitfall 7: Teams Call Records Require Subscription Webhooks for Real-Time Access

**What goes wrong:** The Teams call records API (`/communications/callRecords/{id}`) requires you to know the call record ID in advance. Unlike usage reports that provide aggregate data, individual call records are best accessed via webhook subscriptions (`/subscriptions`) that notify your app when a call completes. Without a webhook, you'd need to enumerate all call records, which is impractical.

**Why it happens:** The call records API is designed around an event-driven model. Microsoft expects you to subscribe to `callRecord` change notifications and process them as they arrive.

**Consequences:** Building call log features without webhooks means either: (1) no individual call details, only aggregate Teams usage reports, or (2) implementing a webhook endpoint on the WhoDis container, which adds complexity (public endpoint, subscription renewal every 3 days max, validation handshake).

**Prevention:**
- For v4.0, scope Teams reporting to aggregate usage reports (`getTeamsUserActivityUserDetail`) which provide daily summaries of calls, meetings, messages per user. This works with the existing sync-and-cache pattern.
- Defer individual call record tracking (which requires webhooks) to a future milestone.
- If call detail is needed, use the `getTeamsUserActivityUserDetail` endpoint with `period='D7'` or `period='D30'` for weekly/monthly summaries.
- `CallRecords.Read.All` is application-only permission -- it cannot be scoped to specific users, which is a security consideration for tenant admin consent.

**Detection:** Attempts to call `/communications/callRecords` without an ID returning 404 or empty results.

**Phase:** Teams reporting phase. Scope decision must happen during planning, not implementation.

### Pitfall 8: Graphviz System Package Bloats Docker Image

**What goes wrong:** Adding `graphviz` as a system package to the Docker image for ER diagram generation adds ~30-50 MB to the image. This directly conflicts with the multi-stage build optimization goal of reducing image size. Additionally, `graphviz` pulls in X11/font dependencies on Debian slim images.

**Why it happens:** Graphviz is a C-based graph visualization tool. The Python `graphviz` package is just a wrapper that calls the `dot` command-line tool, which must be installed as a system package.

**Consequences:** The Docker image gets larger instead of smaller. If using `pygraphviz` (the alternative Python binding), it also requires `graphviz-dev` headers for compilation, further bloating the build.

**Prevention:**
- Use the pure Python `graphviz` package (not `pygraphviz`) -- it generates DOT format and calls the `dot` binary, avoiding compilation headers.
- Alternative: Generate Mermaid.js ER diagram syntax server-side and render client-side in the browser. Zero server dependencies, leverages the existing HTMX pattern, and the Mermaid CDN is already common in documentation tools. This avoids adding any system packages to Docker.
- If Graphviz must be in Docker, install it in the runtime stage with `--no-install-recommends` to minimize pulled dependencies.
- Consider generating diagrams on-demand and caching the SVG output in `report_cache` rather than regenerating on every request.

**Detection:** Docker image size increase after adding graphviz. Run `docker images` before and after.

**Phase:** Schema visualization phase AND Docker optimization phase -- these two features are in tension and should be planned together.

### Pitfall 9: SQLAlchemy Metadata Reflection vs. Model Introspection Mismatch

**What goes wrong:** There are two ways to generate ER diagrams: (1) reflect from the live database using `MetaData.reflect()`, or (2) introspect SQLAlchemy model classes. These can produce different results. The live database may have tables not represented in models (e.g., Alembic's `alembic_version` table, legacy tables), and models may have relationships that aren't enforced by database-level foreign keys.

**Why it happens:** WhoDis uses Alembic for migrations, so the live database schema is authoritative. But the SQLAlchemy models define Python-level relationships that may not have corresponding FK constraints. The 27 tables in the codebase include models with varying levels of relationship definition.

**Consequences:** Diagram shows unexpected tables, missing relationships, or relationships that exist in code but not in the database (or vice versa). The diagram looks wrong or incomplete.

**Prevention:**
- Use database reflection (`MetaData.reflect(bind=engine)`) as the primary source -- it shows what actually exists.
- Filter out known non-application tables (`alembic_version`).
- Optionally overlay SQLAlchemy model relationships as dashed lines to show logical (not physical) relationships.
- With 27 tables, the diagram is manageable but should support zoom/pan in the HTMX UI. Consider grouping by functional area (core, logging, compliance, genesys, workflow).

**Detection:** ER diagram shows tables the team doesn't recognize, or misses known relationships.

**Phase:** Schema visualization phase.

### Pitfall 10: Graph API Rate Limits on Report Endpoints Are Undocumented Per-Endpoint

**What goes wrong:** Microsoft's throttling documentation does not list specific rate limits for usage report endpoints. The global limit is 130,000 requests/10 seconds/app across all tenants, but per-endpoint limits for reports are not published. Bulk report syncs that fetch multiple report types rapidly could hit undocumented throttling.

**Why it happens:** Microsoft does not publish granular rate limits for all endpoint categories. Reports are not listed in the service-specific throttling limits page.

**Consequences:** Intermittent 429 responses during report sync with no clear retry-after guidance. The existing report sync service does not have retry-with-backoff logic for report-specific endpoints.

**Prevention:**
- Add `Retry-After` header handling to report sync requests. Microsoft returns this header on 429 responses.
- Stagger report type syncs (don't fire Exchange + Teams + SharePoint + OneDrive reports simultaneously).
- The existing `ReportSyncService` pattern of caching with TTL (4 hours) is good -- keep the sync interval at daily or every 4 hours, not more frequent.
- Log all 429 responses with the `Retry-After` value so you can tune intervals.

**Detection:** 429 responses in logs during report sync. Monitor the `Retry-After` header values.

**Phase:** All reporting phases. Add retry logic in the foundational reporting infrastructure.

## Minor Pitfalls

### Pitfall 11: Multi-Stage Build Cache Invalidation Slows Dev Workflow

**What goes wrong:** Multi-stage Docker builds can invalidate the pip install cache layer more frequently if the stage structure changes how `requirements.txt` is copied. Developers accustomed to fast rebuilds after code changes may find that any change to the stage structure forces a full pip reinstall.

**Prevention:**
- Keep `COPY requirements.txt .` and `RUN pip install` as the first steps in the builder stage, before `COPY . .` for application code.
- Use `--mount=type=cache,target=/root/.cache/pip` (BuildKit cache mounts) to persist the pip cache across builds.
- Test the rebuild time with and without requirements changes to verify layer caching works.

**Phase:** Docker optimization phase.

### Pitfall 12: SharePoint/OneDrive Storage Reports May Require Site-Level Permissions

**What goes wrong:** While `Reports.Read.All` covers aggregate SharePoint/OneDrive usage reports, some site-level detail endpoints (like `getSharePointSiteUsageDetail`) return site URLs and storage breakdowns. If the tenant has SharePoint sites with restricted access policies, the report may still return aggregate data but individual site details could be filtered.

**Prevention:**
- Start with org-level aggregate reports (`getSharePointSiteUsageSiteCounts`, `getSharePointSiteUsageStorage`) before diving into per-site detail.
- `Reports.Read.All` is sufficient for all standard usage reports -- do not request `Sites.Read.All` unless you need to access site content (you don't).
- Verify report output includes expected site count by cross-referencing with SharePoint admin center.

**Phase:** SharePoint/OneDrive reporting phase.

### Pitfall 13: The `$format=application/json` Parameter Not Supported on All Endpoints

**What goes wrong:** While most v1.0 usage report endpoints support `$format=application/json` to return JSON instead of CSV, some endpoints (particularly older or less common ones) may not support this parameter and will ignore it, still returning CSV.

**Prevention:**
- Build the report parser to handle both JSON and CSV responses gracefully.
- Check the `Content-Type` response header before parsing: `application/json` vs `text/csv`.
- Have a CSV parsing fallback using Python's `csv` module (already imported in `reports.py`).

**Phase:** Foundational reporting infrastructure.

### Pitfall 14: SKU Tooltip XSS via Untrusted Display Names

**What goes wrong:** If SKU friendly names come from Microsoft's CSV or from the Graph API `displayName` field, they could theoretically contain HTML-special characters. Injecting these directly into HTMX tooltip content without escaping could create XSS vulnerabilities.

**Prevention:**
- Use Jinja2's auto-escaping (already enabled in the Flask app) for all tooltip content.
- When storing SKU names in `external_service_data`, validate that they contain only expected characters.
- The existing `escapeHtml()` JavaScript utility should be used for any client-side rendering of SKU names.

**Phase:** SKU tooltips phase. Standard security hygiene.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| SKU Tooltips | #5: Display names not in Graph API | Download Microsoft's CSV mapping; enrich `SkuCatalogCache` |
| SKU Tooltips | #14: XSS in tooltip content | Jinja2 auto-escaping + `escapeHtml()` |
| ER Diagrams | #8: Graphviz bloats Docker image | Use Mermaid.js client-side rendering instead |
| ER Diagrams | #9: Reflection vs model mismatch | Use DB reflection, filter `alembic_version`, overlay model relationships |
| Docker Multi-Stage | #4: ODBC driver missing at runtime | Install ODBC in runtime stage, not builder |
| Docker Multi-Stage | #11: Cache invalidation slows dev | BuildKit cache mounts, proper layer ordering |
| Docker Multi-Stage | #8: Graphviz conflicts with size goal | Plan ER diagrams and Docker optimization together |
| Exchange Reporting | #1: CSV/302 response format | Use `$format=application/json` or build CSV parser |
| Exchange Reporting | #2: Concealed usernames | Pre-flight check `adminReportSettings`, display warning banner |
| Exchange Reporting | #6: Data lag 24-72 hours | Display "Data as of" timestamp, default to 2-day-old date range |
| Teams Reporting | #7: Call records need webhooks | Scope to aggregate usage reports, defer call details |
| Teams Reporting | #3: Permission verification | Test `Reports.Read.All` + `CallRecords.Read.All` before building |
| SharePoint/OneDrive | #12: Site-level permission gaps | Start with org-level aggregates |
| All Reporting | #10: Undocumented rate limits | Retry-After handling, stagger syncs, daily cadence |
| All Reporting | #13: JSON format not universal | Build dual CSV/JSON parser |

## Permission Manifest (Required for v4.0 Reporting)

The following permissions must be added to the Azure AD app registration and granted tenant admin consent BEFORE building reporting features:

| Permission | Type | Required For | Already Granted? |
|------------|------|-------------|-----------------|
| `Reports.Read.All` | Application | Exchange, Teams, SharePoint, OneDrive usage reports | NO -- new |
| `ReportSettings.Read.All` | Application | Check concealed names privacy setting | NO -- new |
| `CallRecords.Read.All` | Application | Teams call records (if individual call detail needed) | NO -- new, defer unless needed |
| `User.Read.All` | Application | Already used for license/user data | YES |
| `Organization.Read.All` | Application | Already used for `subscribedSkus` | YES |
| `AuditLog.Read.All` | Application | Already used for sign-in logs, MFA reports | YES |

**Recommendation:** Request `Reports.Read.All` and `ReportSettings.Read.All` together in one admin consent flow. Defer `CallRecords.Read.All` unless individual call detail is explicitly required.

## Sources

- [Microsoft Graph usage reports overview (v1.0)](https://learn.microsoft.com/en-us/graph/api/resources/report?view=graph-rest-1.0) -- HIGH confidence
- [Microsoft Graph throttling limits](https://learn.microsoft.com/en-us/graph/throttling-limits) -- HIGH confidence (reports not specifically listed)
- [adminReportSettings privacy API](https://office365itpros.com/2024/08/15/usage-reports-api-ga/) -- MEDIUM confidence
- [M365 SKU display name mapping](https://learn.microsoft.com/en-us/entra/identity/users/licensing-service-plan-reference) -- HIGH confidence
- [Microsoft SKU reference CSV](https://rakhesh.com/azure/m365-licensing-displayname-to-sku-name-mapping/) -- MEDIUM confidence
- [pygraphviz Docker issues](https://github.com/pygraphviz/pygraphviz/issues/201) -- HIGH confidence
- [Multi-stage Docker builds for Python](https://pythonspeed.com/articles/multi-stage-docker-python/) -- MEDIUM confidence
- [Teams call records API FAQ](https://learn.microsoft.com/en-us/graph/callrecords-api-faq) -- HIGH confidence
- [Graph API Teams usage report data lag](https://learn.microsoft.com/en-us/answers/questions/1275044/graph-api-teams-user-activity-report-refreshed-mor) -- MEDIUM confidence
- [Graph usage reports CSV/JSON format](https://michev.info/blog/post/3578/microsoft-365-usage-reports-graph-api-adds-a-json-return-type) -- MEDIUM confidence
