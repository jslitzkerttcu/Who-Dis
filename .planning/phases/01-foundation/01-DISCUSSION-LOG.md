# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 01-foundation
**Areas discussed:** Salt file + key rotation, Request ID & log format, Rate limiting + health check, Pagination pattern

---

## Salt File + Key Rotation (SEC-01, SEC-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Rotate + gitignore, keep history | Generate new salt, gitignore, rotate key, re-encrypt config. No history rewrite. | ✓ |
| Rewrite history with git-filter-repo | Purge from all commits, force-push, every clone re-clones. | |
| Both: rewrite AND rotate | Belt-and-suspenders. | |

**User's choice:** Rotate + gitignore, keep history.
**Notes:** Leaked salt becomes useless once the key rotates; avoids force-push coordination on a small team.

| Option | Description | Selected |
|--------|-------------|----------|
| `scripts/rotate_encryption_key.py` | Matches existing scripts/ pattern. | ✓ |
| `flask rotate-key` CLI | Registered via Flask CLI. New pattern for project. | |

**User's choice:** scripts/rotate_encryption_key.py.

| Option | Description | Selected |
|--------|-------------|----------|
| In-place re-encrypt with dual-key window | OLD_KEY + NEW_KEY env vars, transactional re-encrypt, dry-run, verify step. | ✓ |
| Export → swap key → import | Three-step manual process; file is the rollback. | |

**User's choice:** In-place re-encrypt with dual-key window.

---

## Request ID & Log Format (OPS-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Custom middleware + flask.g + LogFilter | ~30 lines, no new dep. Honors existing patterns. | ✓ |
| flask-log-request-id library | Third-party, less code, adds a dep. | |
| structlog + contextvars | Bigger refactor; reformats every logger.* call. | |

**User's choice:** Custom middleware + flask.g + LogFilter.

| Option | Description | Selected |
|--------|-------------|----------|
| Structured JSON via python-json-logger | Parseable JSON, ~5 lines of config. | ✓ |
| Plain text with [request_id] prefix | Easier to read at terminal, harder to aggregate. | |
| Both — JSON in prod, plain in dev | Switch on env. More config surface. | |

**User's choice:** Structured JSON via python-json-logger.

| Option | Description | Selected |
|--------|-------------|----------|
| Honor inbound X-Request-ID + emit response header | Cross-service correlation. | ✓ |
| Always generate fresh | Simpler, loses correlation. | |

**User's choice:** Honor inbound + emit response header.

---

## Rate Limiting + Health Check (SEC-03, OPS-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Flask-Limiter + PostgreSQL backend | Aggregates across gunicorn workers, no Redis dep. | ✓ |
| Flask-Limiter in-memory | Per-worker only, not multi-worker safe. | |
| Custom counter table, no library | Reinvents Flask-Limiter. | |

**User's choice:** Flask-Limiter + PostgreSQL backend.

| Option | Description | Selected |
|--------|-------------|----------|
| 30/minute per user | Generous for IT staff; catches abuse. | ✓ |
| 60/minute per user | More forgiving. | |
| 10/minute per user | Tight; may trigger on legit bursts. | |

**User's choice:** 30/minute per user.

| Option | Description | Selected |
|--------|-------------|----------|
| /health (deep DB) + /health/live (shallow), unauth | Two endpoints, no external API probes. | ✓ |
| /health only with DB + LDAP + Graph + Genesys | Comprehensive, slow, brittle to API outages. | |
| /health only, shallow (process + DB) | Fast, cheap, single endpoint. | |

**User's choice:** /health (deep) + /health/live (shallow), both unauth.
**Notes:** External API health stays behind auth at /admin/api/tokens/status to avoid monitoring red-flagging on transient outages.

---

## Pagination Pattern (OPS-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Page numbers with offset/limit | Bookmarkable URLs, HTMX swap, familiar. | ✓ |
| HTMX 'Load More' button | Append-only; loses jump-to-last. | |
| Infinite scroll | Hides total count, weird back behavior. | |

**User's choice:** Page numbers with offset/limit.

| Option | Description | Selected |
|--------|-------------|----------|
| 50/page, paginate when >100 rows | Matches OPS-04. Selector for 25/50/100. | ✓ |
| 25/page always | More clicks. | |
| 100/page always | Larger payloads. | |

**User's choice:** 50/page, paginate when >100 rows.

---

## Claude's Discretion

The following items were not deeply discussed — sensible defaults applied, captured in CONTEXT.md "Claude's Discretion" subsection:
- DEBT-01 init consolidation
- DEBT-02 DataWarehouseService removal
- DEBT-03 Cache cleanup job approach
- DEBT-04 Asyncio modernization
- OPS-03 Config validation
- OPS-04 Pagination wiring (which tables)
- SEC-04 Auth header configurability

## Deferred Ideas

- Redis-backed rate limiting (future scaling)
- k8s-style readiness probes (deployment platform doesn't require it)
- OpenTelemetry distributed tracing (future milestone)
- API rate limiting per-token (Phase 7 scope)
