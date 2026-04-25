---
phase: 01-foundation
plan: 04
subsystem: middleware/logging
tags: [observability, logging, request-id, ops-02]
requirements: [OPS-02]
dependency_graph:
  requires:
    - flask.g
    - logging (stdlib)
  provides:
    - request_id_propagation
    - json_structured_logging
    - RequestIdFilter
    - init_request_id
  affects:
    - app/__init__.py
tech_stack:
  added:
    - python-json-logger>=2.0.7,<3
  patterns:
    - per-request UUID4 with regex-validated inbound override
    - logging.Filter injecting flask.g.request_id into every LogRecord
    - JSON formatter on root handler (replaces logging.basicConfig)
key_files:
  created:
    - app/middleware/request_id.py
    - .planning/phases/01-foundation/01-04-SUMMARY.md
  modified:
    - app/__init__.py
    - requirements.txt
decisions:
  - Inbound X-Request-ID validated against ^[0-9a-fA-F-]{8,64}$ and truncated to 64 chars to prevent log injection (T-01-04-01)
  - JSON formatter explicitly enumerates fields (timestamp, level, logger, request_id, message) so sensitive extras are not auto-serialized (T-01-04-02)
  - "-" sentinel used for log records emitted outside a request context (background threads, startup) so the request_id field is always present
  - Root handler is rebuilt rather than added to, to avoid duplicate output under the Flask debug reloader
metrics:
  duration_minutes: 4
  completed: 2026-04-25
  tasks_completed: 1
  files_modified: 2
  files_created: 1
  commit_count: 1
---

# Phase 01 Plan 04: Request ID & JSON Logging Summary

Adds per-request correlation IDs and JSON-structured logging so every log line is grep-able to a single request — satisfies OPS-02.

## Outcome

`init_request_id(app)` registers `before_request`/`after_request` hooks that stamp `g.request_id` (honoring well-formed inbound `X-Request-ID`, otherwise UUID4) and echo it back as the `X-Request-ID` response header. `RequestIdFilter` injects that value as `record.request_id` on every `LogRecord`. The root logger now emits JSON via `python-json-logger`'s `JsonFormatter`, with `asctime/levelname/name` renamed to `timestamp/level/logger`. Pre-existing third-party logger quieting (urllib3, msal, simple_config) is preserved.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create request_id middleware + JSON logging wiring | ee55246 | app/middleware/request_id.py, app/__init__.py, requirements.txt |

## Verification

Executed in-process via Flask test client (PostgreSQL not required for the middleware itself):

- Inbound `X-Request-ID: abcd1234abcd1234abcd1234abcd1234` → response header echoes it verbatim
- No inbound header → response header is a fresh 32-char hex UUID4
- Malformed inbound `../../etc/passwd` → rejected, replaced with fresh UUID4
- In-request log line emitted by `logging.getLogger('test').info('hello from test')` was captured as JSON with keys `['level', 'logger', 'message', 'request_id', 'taskName', 'timestamp']`; `request_id` matched the inbound `X-Request-ID` exactly
- `logging.getLogger('urllib3').level == 30` (WARNING) — DEBT-01 quieting preserved

Static checks:

- `ruff check app/middleware/request_id.py app/__init__.py` — clean
- `pip install -r requirements.txt` — installs `python-json-logger-2.0.7` cleanly
- `python -c "import app.middleware.request_id"` — imports clean

## Deviations from Plan

None — plan executed exactly as written. The code template was applied verbatim with one cosmetic refinement: the JSON-logging configuration was extracted into a private helper `_configure_json_logging()` inside `app/__init__.py` to keep `create_app()` readable. Behavior is identical.

## Known Stubs

None.

## Follow-ups (Deferred)

- The verification step in the plan referenced `/health/live`, which is provided by plan 01-03 (not yet executed). Verification was performed against an arbitrary path (`/__nope__`) since `before_request`/`after_request` hooks fire regardless of route match. Once 01-03 ships, the curl-based smoke checks in the plan's `<verification>` block become directly executable.
- `app/__init__.py` still uses `app.logger.error/warning` in some places. These already flow through the root handler (Flask propagates by default), so they are JSON-formatted with request_id, but converting them to module-level `logging.getLogger(__name__)` calls would make logger names more granular. Out of scope for OPS-02.

## Threat Flags

None — no new trust boundaries beyond those documented in the plan's threat model. The X-Request-ID input is validated at the boundary (T-01-04-01 mitigation in place).

## Self-Check: PASSED

- FOUND: app/middleware/request_id.py
- FOUND: app/__init__.py (modified)
- FOUND: requirements.txt (python-json-logger pinned)
- FOUND: commit ee55246
- FOUND: .planning/phases/01-foundation/01-04-SUMMARY.md
