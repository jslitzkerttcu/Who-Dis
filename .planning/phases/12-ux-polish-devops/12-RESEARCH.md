# Phase 12: UX Polish & DevOps - Research

**Researched:** 2026-05-18
**Domain:** Tailwind CSS tooltips, Microsoft Graph API service plans, Docker multi-stage builds
**Confidence:** HIGH

## Summary

Phase 12 has two independent workstreams: (1) enhancing license SKU badges with service plan tooltips, and (2) optimizing the Dockerfile with a multi-stage build. Both are well-understood problems with clear implementation paths.

For the tooltip feature, the Graph API `/subscribedSkus` endpoint already returns `servicePlans` arrays with each SKU, and the existing `SkuCatalogCache` stores the full raw response in the `raw_data` JSONB column of `external_service_data`. Service plans only have technical `servicePlanName` values (e.g., `EXCHANGE_S_ENTERPRISE`), not friendly display names. Microsoft publishes an official CSV mapping file, but a simpler approach exists: build a static Python dictionary mapping the ~50 most common service plan names to friendly labels (e.g., `"EXCHANGE_S_ENTERPRISE"` -> `"Exchange Online (Plan 2)"`), with a fallback to humanizing the technical name by replacing underscores and title-casing. No new API calls or external data sources are needed.

For Docker optimization, the current Dockerfile is a single-stage build on `python:3.12-slim` that installs curl, postgresql-client, unixodbc-dev, gnupg2, and ODBC Driver 18. The multi-stage approach separates build-time dependencies (gnupg2 for GPG key import, unixodbc-dev headers for pyodbc compilation) from runtime dependencies (unixodbc runtime libs, msodbcsql18, postgresql-client for entrypoint pg_isready). The HEALTHCHECK currently uses `curl` which can be replaced with a Python urllib script to avoid installing curl in the runtime stage.

**Primary recommendation:** Extract service plan names from existing `raw_data` JSONB in `SkuCatalogCache`, humanize them with a static mapping dict, pass to template as part of license dicts, and render a Tailwind CSS tooltip. For Docker, split into builder (installs ODBC + compiles pip packages) and runtime (copies only runtime libs + pip packages).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Tooltip shows a service plan breakdown -- the top 5 most recognizable service plans included in the license, plus a "+N more" count if more exist
- **D-02:** Use a styled Tailwind tooltip component, not a native HTML `title` attribute -- enables formatted list rendering with proper styling
- **D-03:** Tooltip does not include the SKU GUID -- plans only. The badge text already shows the friendly display name; the tooltip adds what's inside the license
- **D-04:** Data source is the existing `SkuCatalogCache` service which already stores SKU metadata in `external_service_data` table -- extend it to include service plan names if not already stored
- **D-05:** Keep python:3.12-slim (Debian-based) as the base image -- ODBC Driver 18 has official Debian packages, all dependencies work out of the box
- **D-06:** Exclude `.planning/` directory from `.dockerignore` -- planning artifacts have no runtime purpose
- **D-07:** Manual verification of 30% image size reduction -- document before/after sizes in plan summary, no automated CI gate

### Claude's Discretion
- Docker runtime contents: Claude determines the optimal builder vs runtime stage split. Goal: minimal runtime with only Python + ODBC runtime libs + pip packages + app code. Strip gnupg2 and build-only tools
- Healthcheck approach: Claude picks the best replacement for `curl` in the HEALTHCHECK command (Python script using urllib, wget if available in slim, or keep curl if size impact is negligible)
- ODBC driver installation: Claude determines whether ODBC needs to be installed in both stages or can be copied from builder to runtime

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UXP-01 | User can hover over any license SKU badge on a profile card and see the friendly display name in a tooltip | Service plan data already in `raw_data` JSONB; needs extraction method + template tooltip component |
| DEVOPS-01 | Dockerfile uses multi-stage build with builder and runtime stages, reducing image size by at least 30% | Current single-stage has gnupg2, curl, unixodbc-dev that are build-only; multi-stage removes these from runtime |
| DEVOPS-02 | `.dockerignore` excludes all non-runtime files (tests, docs, .planning, .git, __pycache__, venv) | Current `.dockerignore` already covers most; needs `.planning/` added |
| DEVOPS-03 | Docker build layers are ordered for optimal cache reuse (dependencies before source code) | Current Dockerfile already copies `requirements.txt` before source; multi-stage preserves this pattern |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Service plan data extraction | Backend (Service) | -- | `SkuCatalogCache` already owns SKU data; add method to extract service plans from stored `raw_data` |
| Service plan name humanization | Backend (Service) | -- | Static mapping dict in service layer; no client-side processing needed |
| Tooltip data injection | Backend (Blueprint) | -- | `_build_m365_section_data()` in search blueprint already builds license dicts; extend to include service plans |
| Tooltip rendering | Frontend (Template) | -- | Jinja2 template with Tailwind classes; CSS-first with minimal JS for positioning |
| Docker multi-stage build | Infrastructure | -- | Dockerfile and .dockerignore modifications only |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | CDN (existing) | Tooltip styling with utility classes | Already used throughout project; D-02 mandates Tailwind tooltip [VERIFIED: codebase] |
| Flask/Jinja2 | 3.1.3 (existing) | Template rendering for tooltip HTML | Existing stack, no new dependencies [VERIFIED: requirements.txt] |
| python:3.12-slim | 3.12 | Docker base image (both stages) | D-05 locked decision [VERIFIED: Dockerfile] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| No new packages | -- | -- | This phase requires zero new pip packages or frontend libraries |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Static service plan mapping dict | Microsoft CSV download at refresh time | CSV adds network dependency + parsing complexity for ~50 relevant plans; static dict is simpler and sufficient for IT desk tooltip display |
| Python urllib healthcheck | Keep curl in runtime | curl adds ~10MB to image; urllib is already in Python stdlib |
| CSS-only tooltip | JavaScript tooltip library (tippy.js, etc.) | CSS-only is sufficient per UI-SPEC; falls back to minimal JS only if viewport-aware repositioning needed |

## Package Legitimacy Audit

> No new packages are introduced in this phase. All work uses existing dependencies.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | -- | -- | -- | -- | -- | -- |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Workstream 1: SKU Tooltip
=========================

  [Graph API /subscribedSkus]
         |
         v (daily refresh, already implemented)
  [SkuCatalogCache.refresh()]
         |
         v stores full SKU JSON including servicePlans array
  [external_service_data.raw_data JSONB]
         |
         v NEW: get_service_plans(sku_id) extracts from raw_data
  [SkuCatalogCache]
         |
         v humanize names via static mapping dict
  [_build_m365_section_data()]
         |
         v adds "service_plans" list to each license dict
  [_m365_section.html template]
         |
         v renders Tailwind tooltip on badge hover
  [Browser: CSS hover + optional JS positioning]


Workstream 2: Docker Multi-Stage
=================================

  Stage 1: builder (python:3.12-slim)
  +------------------------------------------+
  | apt: gnupg2, unixodbc-dev, curl (temp)   |
  | ODBC Driver 18 installed via MS repo     |
  | pip install -r requirements.txt          |
  | (build artifacts: .pyc, headers, GPG)    |
  +------------------------------------------+
         |
         v COPY --from=builder
  Stage 2: runtime (python:3.12-slim)
  +------------------------------------------+
  | apt: unixodbc, postgresql-client         |
  | COPY ODBC driver from builder            |
  | COPY pip site-packages from builder      |
  | COPY app source code                     |
  | Python urllib healthcheck script         |
  | Non-root user, ENTRYPOINT               |
  +------------------------------------------+
```

### Recommended Project Structure
```
(No new directories -- modifications to existing files only)

app/services/sku_catalog_cache.py     # Add get_service_plans() method
app/blueprints/search/__init__.py     # Extend _build_m365_section_data()
app/templates/search/_m365_section.html  # Add tooltip HTML to badge loop
scripts/docker_healthcheck.py         # NEW: urllib-based healthcheck
Dockerfile                            # Rewrite as multi-stage
.dockerignore                         # Add .planning/
```

### Pattern 1: Service Plan Data Extraction from Stored JSONB
**What:** The `raw_data` column in `external_service_data` already contains the full Graph API response for each SKU, including `servicePlans` array. No new API call is needed.
**When to use:** When displaying service plan details for a license badge tooltip.
**Example:**
```python
# Source: Existing raw_data structure verified in sku_catalog_cache.py line 100
# Graph API response stored as raw_data includes:
# {
#   "skuId": "...",
#   "skuPartNumber": "ENTERPRISEPACK",
#   "servicePlans": [
#     {"servicePlanName": "EXCHANGE_S_ENTERPRISE", "servicePlanId": "...", ...},
#     {"servicePlanName": "TEAMS1", "servicePlanId": "...", ...},
#   ]
# }

def get_service_plans(self, sku_id: str, limit: int = 5) -> dict:
    """Get humanized service plan names for a SKU.

    Returns {"plans": ["Exchange Online (Plan 2)", ...], "total": 12}
    """
    entry = ExternalServiceData.get_by_service_id("graph", "sku", sku_id)
    if not entry or not entry.raw_data:
        return {"plans": [], "total": 0}

    raw_plans = entry.raw_data.get("servicePlans", [])
    # Filter to user-applicable, successfully provisioned plans
    user_plans = [
        p for p in raw_plans
        if p.get("appliesTo") == "User"
        and p.get("provisioningStatus") == "Success"
    ]
    total = len(user_plans)
    # Humanize and take top N
    humanized = [
        _humanize_service_plan(p.get("servicePlanName", ""))
        for p in user_plans[:limit]
    ]
    return {"plans": humanized, "total": total}
```

### Pattern 2: Service Plan Name Humanization
**What:** Map technical `servicePlanName` values to friendly display names using a static dict.
**When to use:** Always, when displaying service plan names to users.
**Example:**
```python
# Source: Microsoft official mapping reference
# https://learn.microsoft.com/en-us/entra/identity/users/licensing-service-plan-reference

SERVICE_PLAN_FRIENDLY_NAMES = {
    "EXCHANGE_S_ENTERPRISE": "Exchange Online (Plan 2)",
    "TEAMS1": "Microsoft Teams",
    "SHAREPOINTENTERPRISE": "SharePoint Online (Plan 2)",
    "OFFICESUBSCRIPTION": "Microsoft 365 Apps",
    "MCOSTANDARD": "Skype for Business Online (Plan 2)",
    "Deskless": "Microsoft StaffHub",
    "INTUNE_A": "Microsoft Intune",
    "AAD_PREMIUM": "Microsoft Entra ID P1",
    "AAD_PREMIUM_P2": "Microsoft Entra ID P2",
    "RMS_S_ENTERPRISE": "Azure Rights Management",
    "MFA_PREMIUM": "Microsoft Entra ID MFA",
    "POWERAPPS_O365_P2": "Power Apps for Office 365",
    "FLOW_O365_P2": "Power Automate for Office 365",
    "PROJECTWORKMANAGEMENT": "Microsoft Planner",
    "SWAY": "Sway",
    "YAMMER_ENTERPRISE": "Yammer Enterprise",
    # ... ~30-50 most common entries
}

def _humanize_service_plan(plan_name: str) -> str:
    """Convert technical service plan name to friendly display name."""
    if plan_name in SERVICE_PLAN_FRIENDLY_NAMES:
        return SERVICE_PLAN_FRIENDLY_NAMES[plan_name]
    # Fallback: replace underscores, title case, strip trailing numbers
    return plan_name.replace("_", " ").title()
```

### Pattern 3: Docker Multi-Stage with ODBC Driver
**What:** Split Dockerfile into builder and runtime stages, copying only runtime-necessary files.
**When to use:** Always for production Docker builds.
**Example:**
```dockerfile
# Source: Docker multi-stage best practices + MS ODBC docs
# Stage 1: Builder
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
      gnupg2 curl unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] \
       https://packages.microsoft.com/debian/12/prod bookworm main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

# Only runtime ODBC libs (no dev headers, no gnupg2, no curl)
RUN apt-get update && apt-get install -y --no-install-recommends \
      unixodbc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy ODBC driver from builder (avoids re-downloading + gnupg2 in runtime)
COPY --from=builder /opt/microsoft /opt/microsoft
COPY --from=builder /etc/odbcinst.ini /etc/odbcinst.ini

# Copy pip packages from builder
COPY --from=builder /install /usr/local

# ... app code, user, healthcheck, entrypoint
```

### Anti-Patterns to Avoid
- **Installing gnupg2 in runtime stage:** Only needed to verify Microsoft's GPG key during ODBC install. Must stay in builder only.
- **Using `title` attribute for rich tooltips:** Native title cannot render HTML lists or apply styling. D-02 explicitly rejects this.
- **Fetching Microsoft CSV at runtime:** Service plan name mapping should be a static dict, not a runtime download dependency.
- **Installing curl just for healthcheck:** Use Python urllib from stdlib instead; saves ~10MB in final image.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tooltip show/hide | Custom event listeners from scratch | Tailwind `group-hover` with CSS transitions + minimal JS for viewport awareness | CSS-first approach is more reliable; JS only for edge cases (viewport bounds) |
| Service plan name mapping | API call to Microsoft licensing endpoint | Static Python dict from official reference CSV | No runtime dependency; ~50 common plans cover 95%+ of real tenants |
| Docker layer caching | Manual apt cache management | Multi-stage build with `--no-install-recommends` and `rm -rf /var/lib/apt/lists/*` | Docker best practice; automatic cleanup between stages |

## Common Pitfalls

### Pitfall 1: ODBC Driver Copy Between Stages
**What goes wrong:** Copying only `/opt/microsoft/msodbcsql18/` without the ODBC config file breaks pyodbc at runtime.
**Why it happens:** The ODBC driver registers itself in `/etc/odbcinst.ini` during `apt install`. This file is not under `/opt/microsoft/`.
**How to avoid:** Copy both `/opt/microsoft/` (driver binaries) AND `/etc/odbcinst.ini` (driver registration) from builder to runtime. Also ensure `unixodbc` (not `unixodbc-dev`) is installed in runtime for the shared libraries.
**Warning signs:** `pyodbc.Error: ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 18 for SQL Server'")` at runtime.

### Pitfall 2: Service Plans Array May Be Empty or Missing
**What goes wrong:** Some SKUs have no `servicePlans` key in the Graph response, or the array is empty.
**Why it happens:** Free/trial SKUs or very old subscriptions may lack plan details.
**How to avoid:** Always use `.get("servicePlans", [])` and handle empty results gracefully. Template shows "No service plan details available" per UI-SPEC.
**Warning signs:** Empty tooltip or template error on specific license badges.

### Pitfall 3: Tooltip Z-Index and Overflow Clipping
**What goes wrong:** Tooltip appears behind adjacent elements or gets clipped by parent container overflow.
**Why it happens:** The license badges are inside a `flex-wrap` container with potential overflow constraints.
**How to avoid:** Set tooltip `z-index: 50` (Tailwind `z-50`) and ensure parent containers don't have `overflow: hidden`. Position tooltip with `position: absolute` relative to badge (`position: relative` on badge wrapper).
**Warning signs:** Tooltip partially hidden or appearing behind other UI elements.

### Pitfall 4: pip --prefix Install Path Mismatch
**What goes wrong:** Packages installed with `--prefix=/install` in builder don't resolve in runtime when copied to `/usr/local`.
**Why it happens:** Python site-packages path may differ between `--prefix` target and runtime Python's `sys.path`.
**How to avoid:** Use `pip install --no-cache-dir --prefix=/install -r requirements.txt` in builder, then `COPY --from=builder /install /usr/local` in runtime. Verify with `python -c "import flask"` in a test build.
**Warning signs:** `ModuleNotFoundError` when container starts.

### Pitfall 5: postgresql-client Required in Runtime
**What goes wrong:** Container fails to start because `pg_isready` is not found.
**Why it happens:** The `docker-entrypoint.sh` uses `pg_isready` to wait for database readiness before running Alembic migrations.
**How to avoid:** Keep `postgresql-client` in the runtime stage (not just builder).
**Warning signs:** Container crash-loops with "pg_isready: command not found".

## Code Examples

### Tooltip Template HTML (Tailwind CSS)
```jinja2
{# Source: UI-SPEC.md tooltip component specification #}
{% for lic in data.get('licenses', []) %}
  <span class="relative group/badge inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
        {% if lic.get('service_plans') %}aria-describedby="tooltip-{{ lic.get('skuId') }}"{% endif %}>
    {{ lic.get('displayName') or lic.get('name') or lic.get('skuId') }}

    {# Tooltip: service plan breakdown (D-01, D-02, D-03) #}
    {% if lic.get('service_plans') and lic.get('service_plans').get('plans') %}
    <div id="tooltip-{{ lic.get('skuId') }}"
         role="tooltip"
         class="absolute left-1/2 -translate-x-1/2 top-full mt-2
                bg-gray-900 text-gray-100 rounded-md px-2 py-2
                min-w-[200px] max-w-[280px] text-[11px]
                opacity-0 invisible group-hover/badge:opacity-100 group-hover/badge:visible
                transition-opacity duration-150 ease-in-out z-50
                pointer-events-none group-hover/badge:pointer-events-auto">
      {# Arrow #}
      <div class="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-gray-900 rotate-45"></div>

      <div class="font-semibold text-white text-xs mb-1">
        {{ lic.get('displayName') or lic.get('name') }}
      </div>
      <ul class="space-y-0.5">
        {% for plan in lic.get('service_plans', {}).get('plans', []) %}
          <li class="flex items-start gap-1">
            <span class="text-gray-400 mt-px">*</span>
            <span>{{ plan }}</span>
          </li>
        {% endfor %}
      </ul>
      {% set remaining = lic.get('service_plans', {}).get('total', 0) - lic.get('service_plans', {}).get('plans', [])|length %}
      {% if remaining > 0 %}
        <div class="text-gray-400 mt-1">+{{ remaining }} more service plans</div>
      {% endif %}
    </div>
    {% endif %}

    {# Admin remove button (existing, unchanged) #}
    {% if g.role == 'admin' %}
    <button type="button" ...>...</button>
    {% endif %}
  </span>
{% endfor %}
```

### Python urllib Healthcheck Script
```python
#!/usr/bin/env python3
# scripts/docker_healthcheck.py -- stdlib-only healthcheck for Docker
# Replaces curl dependency in HEALTHCHECK directive
import sys
import urllib.request

try:
    resp = urllib.request.urlopen("http://localhost:5000/health", timeout=5)
    sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
```

### Dockerfile HEALTHCHECK Replacement
```dockerfile
COPY scripts/docker_healthcheck.py /usr/local/bin/healthcheck.py
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python /usr/local/bin/healthcheck.py || exit 1
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `title` attribute for tooltips | CSS-driven styled tooltips with Tailwind | Ongoing | Better UX, accessibility, formatted content |
| Single-stage Dockerfile | Multi-stage builds | Docker 17.05 (2017) | Smaller images, better security, faster deploys |
| curl in HEALTHCHECK | Python urllib / wget | Best practice evolution | Eliminates unnecessary runtime dependency |
| `unixodbc-dev` in runtime | `unixodbc` only (runtime libs) | Always was best practice | -dev headers not needed at runtime; saves ~5MB |

**Deprecated/outdated:**
- `gnupg2` in final image: Only needed for GPG key verification during ODBC install; should not persist in runtime
- Native HTML `title` for rich content: Cannot render lists or apply styling; rejected by D-02

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Flask/PostgreSQL/HTMX -- extend existing patterns, do not introduce new frameworks
- **Auth:** Azure AD SSO only -- not relevant to this phase (tooltip is display-only, Docker is infra)
- **Security:** All write operations require audit trail -- not relevant (no write operations in this phase)
- **Code style:** ruff check, mypy type checking, 4-space indentation, double quotes
- **Dependency injection:** Services accessed via `current_app.container.get()`, never global imports
- **Error handling:** Use `@handle_service_errors` decorator on service methods
- **Frontend:** Tailwind CSS utility classes, no custom CSS files; HTMX for dynamic content; minimal vanilla JS

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Static dict of ~50 service plan friendly names covers 95%+ of real tenant licenses | Architecture Patterns | If tenant has unusual plans, fallback humanization (title-case) may look awkward but functional |
| A2 | ODBC driver files can be copied from builder via `/opt/microsoft/` + `/etc/odbcinst.ini` | Pitfalls | If ODBC installs to different paths on current Debian 12, the copy will fail; verify paths in builder stage |
| A3 | Removing curl + gnupg2 + unixodbc-dev achieves 30%+ image size reduction | Architecture Patterns | If base image overhead dominates, savings may be less; D-07 mandates manual size check |
| A4 | `pip install --prefix=/install` produces packages compatible with runtime Python sys.path when copied to `/usr/local` | Pitfalls | If path mismatch, need to use `--target` instead and set PYTHONPATH |

## Open Questions

1. **Exact ODBC driver file paths on Debian 12 bookworm**
   - What we know: ODBC installs to `/opt/microsoft/msodbcsql18/` and registers in `/etc/odbcinst.ini` [ASSUMED]
   - What's unclear: Whether there are additional symlinks or config files needed
   - Recommendation: Verify paths in builder stage during implementation with `dpkg -L msodbcsql18`

2. **Service plan filtering strategy for "top 5 most recognizable"**
   - What we know: D-01 says "top 5 most recognizable service plans"
   - What's unclear: Whether "recognizable" means alphabetical, by a priority ranking, or just first 5 user-applicable plans
   - Recommendation: Filter to `appliesTo == "User"` and `provisioningStatus == "Success"`, then sort by a hardcoded priority list of well-known plans (Exchange, Teams, SharePoint, Office apps first), take top 5

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | DEVOPS-01/02/03 | Yes | 29.4.0 | -- |
| Docker Buildx | Multi-stage build | Yes | 0.33.0 | Standard `docker build` also supports multi-stage |
| Python 3.x | Development/testing | Yes | (system) | -- |
| ruff | Code quality | Yes (in requirements) | -- | -- |
| mypy | Type checking | Yes (in requirements) | -- | -- |
| pytest | Testing | Yes (in pyproject.toml) | -- | -- |

**Missing dependencies with no fallback:** None
**Missing dependencies with fallback:** None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (configured in pyproject.toml) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `pytest tests/unit -x -q` |
| Full suite command | `pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UXP-01 | `get_service_plans()` returns humanized plan names from raw_data | unit | `pytest tests/unit/test_sku_catalog_cache.py -x` | Needs Wave 0 |
| UXP-01 | `_humanize_service_plan()` maps technical names to friendly names | unit | `pytest tests/unit/test_sku_catalog_cache.py -x` | Needs Wave 0 |
| UXP-01 | `_build_m365_section_data()` includes service_plans in license dicts | unit | `pytest tests/unit/test_search_blueprint.py -x` | Needs Wave 0 |
| DEVOPS-01 | Dockerfile builds successfully with multi-stage | manual-only | `docker build -t whodis:test .` | N/A (manual) |
| DEVOPS-01 | Runtime image is 30%+ smaller than current | manual-only | `docker images whodis` | N/A (manual, per D-07) |
| DEVOPS-02 | .dockerignore excludes .planning/ | manual-only | Inspect with `docker build` context | N/A |
| DEVOPS-03 | Layer ordering: requirements.txt before source copy | manual-only | Inspect Dockerfile | N/A |

### Sampling Rate
- **Per task commit:** `pytest tests/unit -x -q`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_sku_catalog_cache.py` -- covers UXP-01 service plan extraction and humanization
- [ ] Test fixtures for ExternalServiceData with raw_data containing servicePlans array

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not affected (display-only feature + infra) |
| V3 Session Management | No | Not affected |
| V4 Access Control | No | Existing auth decorators remain unchanged |
| V5 Input Validation | No | Service plan data comes from trusted Graph API cache, not user input |
| V6 Cryptography | No | Not affected |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via service plan names in tooltip | Tampering | Jinja2 auto-escaping (enabled by default in Flask) |
| Docker image with unnecessary attack surface | Elevation of Privilege | Multi-stage build removes build tools from runtime |
| Non-root container user bypass | Elevation of Privilege | Existing `USER app` directive preserved in runtime stage |

## Sources

### Primary (HIGH confidence)
- [Microsoft Graph subscribedSku resource](https://learn.microsoft.com/en-us/graph/api/resources/subscribedsku?view=graph-rest-1.0) -- servicePlans array structure confirmed
- [Microsoft Graph servicePlanInfo resource](https://learn.microsoft.com/en-us/graph/api/resources/serviceplaninfo?view=graph-rest-1.0) -- properties: servicePlanId, servicePlanName, provisioningStatus, appliesTo (NO displayName field)
- [Microsoft service plan reference CSV](https://learn.microsoft.com/en-us/entra/identity/users/licensing-service-plan-reference) -- official mapping of servicePlanName to friendly display names
- Codebase inspection: `app/services/sku_catalog_cache.py`, `app/models/external_service.py`, `app/blueprints/search/__init__.py`, `app/templates/search/_m365_section.html`, `Dockerfile`, `.dockerignore`

### Secondary (MEDIUM confidence)
- Docker multi-stage build best practices -- well-documented standard approach
- ODBC Driver 18 Debian package paths -- `/opt/microsoft/` is standard MS install location [ASSUMED, verify during implementation]

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new packages, extends existing codebase
- Architecture: HIGH -- both workstreams are well-understood patterns with clear existing code to extend
- Pitfalls: HIGH -- ODBC copy and pip prefix are documented gotchas; service plan data structure confirmed via Microsoft docs

**Research date:** 2026-05-18
**Valid until:** 2026-06-18 (stable domain, no fast-moving dependencies)
