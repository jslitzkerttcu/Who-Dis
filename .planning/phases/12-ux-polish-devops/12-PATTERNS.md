# Phase 12: UX Polish & DevOps - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 6 (4 modified, 2 new)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/services/sku_catalog_cache.py` | service | CRUD (read) | Self (existing file) | exact |
| `app/blueprints/search/__init__.py` | controller | request-response | Self (existing `_build_m365_section_data`) | exact |
| `app/templates/search/_m365_section.html` | component | request-response | Self (existing badge loop lines 104-131) | exact |
| `scripts/docker_healthcheck.py` | utility | request-response | `scripts/verify_deployment.py` | role-match |
| `Dockerfile` | config | batch | Self (existing single-stage) | exact |
| `.dockerignore` | config | N/A | Self (existing) | exact |

## Pattern Assignments

### `app/services/sku_catalog_cache.py` (service, CRUD read — MODIFY)

**Analog:** Self — add `get_service_plans()` method following the existing `get_sku_name()` pattern.

**Imports pattern** (lines 1-7 — reuse existing, no new imports needed):
```python
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

from flask import current_app
from sqlalchemy import text

from app.database import db
from app.services.base import BaseConfigurableService
from app.models.external_service import ExternalServiceData
```

**Core data access pattern** (lines 115-117 — `get_sku_name` uses `ExternalServiceData.get_name_by_id`):
```python
def get_sku_name(self, sku_id: str) -> Optional[str]:
    """Resolve a SKU GUID to its friendly skuPartNumber, or None if unknown."""
    return ExternalServiceData.get_name_by_id("graph", "sku", sku_id)
```

**New method should follow same pattern** — use `ExternalServiceData.get_by_service_id()` to access `raw_data` JSONB, then extract `servicePlans` array. The model method signature (from `app/models/external_service.py` lines 55-61):
```python
@classmethod
def get_by_service_id(
    cls, service_name: str, data_type: str, service_id: str
) -> Optional["ExternalServiceData"]:
    """Get specific data by service ID."""
    return cls.query.filter_by(
        service_name=service_name, data_type=data_type, service_id=service_id
    ).first()
```

**Error handling pattern** (lines 107-113 — swallow errors, log, rollback):
```python
except Exception as e:
    logger.error(f"Error refreshing SKU catalog: {str(e)}", exc_info=True)
    try:
        db.session.rollback()
    except Exception:
        pass
```

**raw_data storage** (lines 90-101 — full Graph SKU JSON stored in raw_data, including servicePlans array):
```python
ExternalServiceData.update_service_data(
    service_name="graph",
    data_type="sku",
    service_id=sku_id,
    name=sku.get("skuPartNumber"),
    description=sku.get("displayName"),
    raw_data=sku,  # Full Graph response including servicePlans array
)
```

---

### `app/blueprints/search/__init__.py` (controller, request-response — MODIFY)

**Analog:** Self — extend `_build_m365_section_data()` at lines 886-908 where license dicts are built.

**License dict construction pattern** (lines 886-908):
```python
# Licenses (D-04, D-05) — resolve SKU GUIDs via sku_catalog.
licenses = []
raw_licenses = user_profile.get("assignedLicenses") or []
if isinstance(raw_licenses, list):
    for lic in raw_licenses:
        if not isinstance(lic, dict):
            continue
        sku_id = lic.get("skuId")
        if not sku_id:
            continue
        friendly = None
        if sku_catalog is not None:
            try:
                friendly = sku_catalog.get_sku_name(sku_id)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"sku_catalog lookup failed for {sku_id}: {e}")
        licenses.append(
            {
                "name": friendly or sku_id,
                "displayName": friendly or sku_id,
                "skuId": sku_id,
            }
        )
```

**Modification point:** After building each license dict, add a `service_plans` key by calling `sku_catalog.get_service_plans(sku_id)`. Follow the same try/except pattern used for `get_sku_name` (line 900-901).

**How sku_catalog is passed in** (line 773):
```python
data = _build_m365_section_data(user, mfa_result, sku_catalog)
```

---

### `app/templates/search/_m365_section.html` (component, request-response — MODIFY)

**Analog:** Self — modify the license badge loop at lines 104-131.

**Current badge rendering pattern** (lines 106-131):
```jinja2
{% for lic in data.get('licenses', []) %}
  <span class="relative group inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
        title="{{ lic.get('skuId') }}">
    {{ lic.get('displayName') or lic.get('name') or lic.get('skuId') }}
    {% if g.role == 'admin' %}
    <button type="button"
            class="absolute -top-1 -right-1 w-4 h-4 bg-red-100 text-red-600 rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
            title="Remove {{ lic.get('displayName') or lic.get('name') }}"
            onclick="event.stopPropagation(); openWriteModal({...})">
      <i class="fas fa-times" style="font-size: 8px;"></i>
    </button>
    {% endif %}
  </span>
{% endfor %}
```

**Key modifications:**
1. Replace `title="{{ lic.get('skuId') }}"` with the Tailwind tooltip `div`
2. Change `group` to `group/badge` to avoid conflict with admin button's group-hover (the admin remove button already uses `group-hover:opacity-100`)
3. Insert tooltip div between the display name text and the admin button
4. Tooltip uses `group-hover/badge:opacity-100` and `group-hover/badge:visible` for show/hide

**Existing Tailwind badge pattern** (from MFA badges, lines 83-89 — same file, same styling approach):
```jinja2
<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
  <i class="fas fa-shield-alt mr-1"></i>{{ m.get('type') }}
</span>
```

---

### `scripts/docker_healthcheck.py` (utility, request-response — NEW)

**Analog:** `scripts/verify_deployment.py` (lines 1-16 for script structure)

**Script header pattern** (verify_deployment.py lines 1-16):
```python
#!/usr/bin/env python3
"""
Deployment Verification Script
=============================

Verifies that the WhoDis employee_profiles consolidation deployment is working correctly.

Usage:
    python scripts/verify_deployment.py [--skip-photos] [--verbose]
"""

import os
import sys
```

**Healthcheck is much simpler** — stdlib-only (no Flask, no project imports). Follow the pattern from RESEARCH.md: `urllib.request.urlopen` with timeout, exit 0/1.

---

### `Dockerfile` (config, batch — MODIFY)

**Analog:** Self — current single-stage at lines 1-42.

**Current layer ordering pattern** (lines 1-42):
```dockerfile
FROM python:3.12-slim
RUN groupadd -r app && useradd -r -g app -u 10001 app
WORKDIR /app

# System deps + ODBC
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl postgresql-client unixodbc-dev gnupg2 \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    ...

# Pip deps (cache-friendly layer — before source code)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code (changes most frequently — last layer)
COPY . .
RUN chmod +x ./docker-entrypoint.sh && chown -R app:app /app

USER app
EXPOSE 5000
HEALTHCHECK ...
ENV ...
ENTRYPOINT ["./docker-entrypoint.sh"]
```

**Patterns to preserve in multi-stage rewrite:**
- Non-root user creation (line 5): `groupadd -r app && useradd -r -g app -u 10001 app`
- `requirements.txt` before source code for layer caching (lines 23-24)
- `chmod +x ./docker-entrypoint.sh` and `chown -R app:app /app` (line 27)
- `USER app` before EXPOSE/ENTRYPOINT (line 30)
- Entrypoint uses `pg_isready` from `postgresql-client` (docker-entrypoint.sh line 20)

**What moves to builder only:** gnupg2, curl, unixodbc-dev (build headers)
**What stays in runtime:** unixodbc (runtime libs), postgresql-client, msodbcsql18 (copied from builder)
**HEALTHCHECK replacement:** `python /usr/local/bin/healthcheck.py` instead of `curl`

---

### `.dockerignore` (config — MODIFY)

**Analog:** Self — current file.

**Current pattern** (all 21 lines):
```
.git
.github
.gitignore
__pycache__
*.pyc
.pytest_cache
.mypy_cache
.ruff_cache
.venv
venv
.env
.env.*
!.env.sandcastle.example
tests/
docs/
*.md
node_modules
.idea
.vscode
.coverage
htmlcov/
```

**Modification:** Add `.planning/` line (per D-06). Place after `docs/` to maintain alphabetical grouping of directory exclusions.

---

## Shared Patterns

### Defensive `.get()` Access
**Source:** `app/templates/search/_m365_section.html` line 19, `app/blueprints/search/__init__.py` line 833
**Apply to:** All template tooltip code and service plan extraction

Every data access in templates and the `_build_m365_section_data` helper uses `.get()` with fallback defaults. The tooltip must follow this pattern:
```jinja2
{% for plan in lic.get('service_plans', {}).get('plans', []) %}
```
```python
raw_plans = entry.raw_data.get("servicePlans", [])
```

### Service Method Error Handling
**Source:** `app/services/sku_catalog_cache.py` lines 62-65 (needs_refresh), 107-113 (refresh)
**Apply to:** New `get_service_plans()` method

```python
except Exception as e:
    logger.error(f"Error ...: {str(e)}", exc_info=True)
    return {"plans": [], "total": 0}  # Graceful degradation
```

### BaseConfigurableService Extension
**Source:** `app/services/base.py` (inherited by sku_catalog_cache.py)
**Apply to:** `get_service_plans()` — no config needed for this method, but it lives on a `BaseConfigurableService` subclass. Use `self._get_config()` if any behavior becomes configurable (e.g., default plan limit).

### Module Logger
**Source:** `app/services/sku_catalog_cache.py` line 9
**Apply to:** All modified Python files already have loggers. New `docker_healthcheck.py` does not need one (stdlib-only, exit code signals health).

```python
logger = logging.getLogger(__name__)
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files have direct analogs (mostly self-modification of existing files) |

## Metadata

**Analog search scope:** `app/services/`, `app/blueprints/search/`, `app/templates/search/`, `app/models/`, `scripts/`, project root (Dockerfile, .dockerignore)
**Files scanned:** 8 (direct reads of canonical references + model)
**Pattern extraction date:** 2026-05-18
