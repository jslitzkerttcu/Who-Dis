---
phase: 12-ux-polish-devops
plan: 02
subsystem: infrastructure
tags: [docker, multi-stage-build, healthcheck, devops]
dependency_graph:
  requires: []
  provides: [multi-stage-dockerfile, python-healthcheck, dockerignore-planning-exclusion]
  affects: [Dockerfile, .dockerignore, scripts/docker_healthcheck.py]
tech_stack:
  added: []
  patterns: [multi-stage-docker-build, stdlib-only-healthcheck, layer-cache-optimization]
key_files:
  created:
    - scripts/docker_healthcheck.py
  modified:
    - Dockerfile
    - .dockerignore
decisions:
  - "ODBC driver copied from builder via /opt/microsoft and /etc/odbcinst.ini (avoids gnupg2/curl in runtime)"
  - "Healthcheck uses Python urllib (stdlib) instead of curl, eliminating curl from runtime image"
  - "pip install uses --prefix=/install in builder, copied to /usr/local in runtime"
metrics:
  duration: 117s
  completed: 2026-05-19T03:55:00Z
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Phase 12 Plan 02: Docker Multi-Stage Build Summary

Multi-stage Dockerfile with builder/runtime separation, Python stdlib healthcheck replacing curl, and .planning/ excluded from Docker context.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Create Python healthcheck script and update .dockerignore | b4c96d9 | scripts/docker_healthcheck.py, .dockerignore |
| 2 | Rewrite Dockerfile as multi-stage build | d85192f | Dockerfile |

## What Was Built

### Task 1: Python Healthcheck Script + .dockerignore Update
- Created `scripts/docker_healthcheck.py`: 10-line stdlib-only script using `urllib.request.urlopen` to check `http://localhost:5000/health` with 5-second timeout. Exits 0 on HTTP 200, exits 1 on any failure.
- Added `.planning/` to `.dockerignore` after the `docs/` line (D-06), preventing planning artifacts from being included in the Docker build context.

### Task 2: Multi-Stage Dockerfile
- **Builder stage** (`python:3.12-slim AS builder`): Installs gnupg2, curl, unixodbc-dev; imports Microsoft GPG key; installs ODBC Driver 18; runs `pip install --no-cache-dir --prefix=/install`.
- **Runtime stage** (`python:3.12-slim`): Installs only `unixodbc` and `postgresql-client`. Copies from builder: `/opt/microsoft` (ODBC driver binaries), `/etc/odbcinst.ini` (ODBC registration), `/install` -> `/usr/local` (pip packages).
- Layer ordering: `requirements.txt` copied and installed before source code in both stages (DEVOPS-03).
- HEALTHCHECK uses `python /usr/local/bin/healthcheck.py` instead of `curl`.
- Non-root user `app` (uid 10001) preserved.
- All existing ENV variables preserved (FLASK_ENV, GUNICORN_WORKERS, PYTHONUNBUFFERED).

## Verification Results

- Dockerfile contains exactly 2 FROM directives (1 AS builder, 1 runtime): PASS
- Builder stage installs gnupg2, curl, unixodbc-dev: PASS
- Runtime stage does NOT install gnupg2, curl, or unixodbc-dev: PASS
- Runtime stage installs unixodbc and postgresql-client: PASS
- COPY --from=builder appears 3 times: PASS
- requirements.txt copied before source code in builder: PASS
- HEALTHCHECK references healthcheck.py (not curl): PASS
- USER app directive present: PASS
- ENTRYPOINT references docker-entrypoint.sh: PASS
- .dockerignore contains .planning/: PASS
- Healthcheck script is stdlib-only (sys, urllib.request): PASS
- ruff check passes on healthcheck script: PASS

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None -- all functionality is complete and wired.

## Decisions Made

1. **ODBC copy strategy**: Copy both `/opt/microsoft` (driver binaries) and `/etc/odbcinst.ini` (driver registration) from builder per RESEARCH.md Pitfall 1.
2. **pip prefix install**: Use `--prefix=/install` in builder, `COPY --from=builder /install /usr/local` in runtime per RESEARCH.md Pattern 3.
3. **Healthcheck placement**: Script copied to `/usr/local/bin/healthcheck.py` outside the app directory for clean separation.

## Manual Verification Required

- `docker build -t whodis:test .` should succeed (D-07, verified in Plan 03 checkpoint)
- Before/after image size comparison to confirm 30%+ reduction (D-07)
