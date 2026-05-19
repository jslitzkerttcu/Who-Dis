# Phase 12: UX Polish & DevOps - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Profile cards show human-readable license names on hover with service plan details, and the Docker image is lean and cache-optimized for fast deployments. Two independent workstreams: SKU tooltip enhancement (UXP-01) and Docker multi-stage build optimization (DEVOPS-01, DEVOPS-02, DEVOPS-03).

</domain>

<decisions>
## Implementation Decisions

### SKU Tooltip Content
- **D-01:** Tooltip shows a **service plan breakdown** — the top 5 most recognizable service plans included in the license, plus a "+N more" count if more exist
- **D-02:** Use a **styled Tailwind tooltip component**, not a native HTML `title` attribute — enables formatted list rendering with proper styling
- **D-03:** Tooltip does **not** include the SKU GUID — plans only. The badge text already shows the friendly display name; the tooltip adds what's *inside* the license
- **D-04:** Data source is the existing `SkuCatalogCache` service which already stores SKU metadata in `external_service_data` table — extend it to include service plan names if not already stored

### Docker Multi-Stage Build
- **D-05:** Keep **python:3.12-slim** (Debian-based) as the base image — ODBC Driver 18 has official Debian packages, all dependencies work out of the box
- **D-06:** Exclude `.planning/` directory from `.dockerignore` — planning artifacts have no runtime purpose
- **D-07:** **Manual verification** of 30% image size reduction — document before/after sizes in plan summary, no automated CI gate

### Claude's Discretion
- **Docker runtime contents:** Claude determines the optimal builder vs runtime stage split. Goal: minimal runtime with only Python + ODBC runtime libs + pip packages + app code. Strip gnupg2 and build-only tools
- **Healthcheck approach:** Claude picks the best replacement for `curl` in the HEALTHCHECK command (Python script using urllib, wget if available in slim, or keep curl if size impact is negligible)
- **ODBC driver installation:** Claude determines whether ODBC needs to be installed in both stages or can be copied from builder to runtime

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SKU Tooltip Feature
- `app/services/sku_catalog_cache.py` — SKU GUID → friendly name catalog; check if service plan data is already stored or needs to be added to the Graph API call
- `app/templates/search/_m365_section.html` lines 104-125 — Current license badge rendering with `title="{{ lic.get('skuId') }}"` that needs tooltip replacement
- `app/services/graph_service.py` — Graph API integration; `/subscribedSkus` endpoint returns service plan data

### Docker Optimization
- `Dockerfile` — Current single-stage build with ODBC Driver 18, gnupg2, curl, postgresql-client
- `.dockerignore` — Current exclusions (tests, docs, *.md, .git, venv) — needs .planning/ added
- `docker-entrypoint.sh` — Entrypoint script referenced by Dockerfile

### Project Context
- `.planning/REQUIREMENTS.md` — UXP-01, DEVOPS-01, DEVOPS-02, DEVOPS-03 requirement definitions
- `.planning/ROADMAP.md` — Phase 12 success criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SkuCatalogCache` service (`app/services/sku_catalog_cache.py`): Already maps SKU GUIDs to friendly names via Graph `/subscribedSkus`. May need extension to store service plan names per SKU
- `ExternalServiceData` model: Stores cached external data with `service_name='graph'`, `data_type='sku'` — the JSONB `data` column can hold service plan arrays
- License badge rendering in `_m365_section.html`: Existing badge structure with `title` attribute — tooltip replaces the `title` with a styled component

### Established Patterns
- Tailwind CSS utility classes for all UI components — tooltip should follow the same approach (no custom CSS files)
- HTMX progressive enhancement — tooltip should work without JS if possible, but a small vanilla JS snippet for show/hide is acceptable given the team already uses minimal JS
- `BaseConfigurableService` pattern — SkuCatalogCache already extends this for config access

### Integration Points
- `_m365_section.html` template: Where tooltip HTML gets added (around license badge loop at lines 104-125)
- `SkuCatalogCache.resolve()` or equivalent: Service method that tooltip data source calls to get service plans per SKU
- `container.py`: SkuCatalogCache already registered — no new registration needed
- `Dockerfile` and `.dockerignore`: Direct modification targets for Docker optimization

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-UX Polish & DevOps*
*Context gathered: 2026-05-18*
