---
phase: 10-rest-api
plan: 01
subsystem: api
tags: [rest-api, auth, tokens, schemas, flask-smorest, openapi]
dependency_graph:
  requires: []
  provides: [external-api-token-model, token-service, bearer-auth, marshmallow-schemas, api-error-handlers, flask-smorest-init]
  affects: [app/__init__.py, app/container.py, requirements.txt]
tech_stack:
  added: [flask-smorest-0.47.0, marshmallow, webargs, apispec]
  patterns: [bearer-token-auth, sha256-token-hashing, d07-error-envelope, d04-response-envelope]
key_files:
  created:
    - app/models/external_api_token.py
    - app/services/external_api_token_service.py
    - alembic/versions/004_external_api_tokens.py
    - app/blueprints/api/__init__.py
    - app/blueprints/api/auth.py
    - app/blueprints/api/schemas.py
    - app/blueprints/api/errors.py
  modified:
    - app/container.py
    - app/__init__.py
    - requirements.txt
decisions:
  - "flask-smorest error handlers registered on app (not blueprint) to catch all /api/v1/* errors"
  - "API token g.user set to 'api:{token.name}' for audit trail compatibility (Pitfall 4)"
metrics:
  duration: 4m 20s
  completed: "2026-05-18T00:17:13Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 3
---

# Phase 10 Plan 01: REST API Foundation Summary

**One-liner:** Bearer token auth with SHA-256 hashed tokens, marshmallow D-04/D-07 schemas, and flask-smorest OpenAPI wiring at /api/v1/docs

## What Was Built

### Task 1: ExternalApiToken Model, Service, and Migration
- **ExternalApiToken** model with SHA-256 hashed tokens (secrets.token_hex(32)), 8-char prefix for display, usage tracking (count + last_used_at), and revocation support
- **ExternalApiTokenService** with create, validate, revoke, list, and get_by_id operations registered in DI container
- **Alembic migration 004** creates external_api_tokens table with unique index on token_hash and index on is_revoked
- **flask-smorest==0.47.0** added to requirements.txt (pulls marshmallow, webargs, apispec as transitive deps)

### Task 2: Bearer Auth, Schemas, Error Handlers, flask-smorest Init
- **require_api_token** decorator extracts bearer token from Authorization header, hashes with SHA-256, validates against DB, calls record_usage(), sets g.api_token and g.user
- **Marshmallow schemas**: MetaSchema, ErrorDetailSchema, SearchResultItemSchema, SearchQuerySchema, SearchResponseSchema, ProfileResponseSchema, ErrorResponseSchema
- **API error handlers** for 400/401/403/404/422/429/500 returning D-07 JSON envelope; 429 includes Retry-After header per API-05
- **init_api(app)** configures flask-smorest Api with OpenAPI 3.0.3 spec and Swagger UI at /api/v1/docs
- **app/__init__.py** calls init_api(app) after limiter.init_app() and before blueprint registrations

## Commits

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | ExternalApiToken model, service, migration | 782e67f | external_api_token.py, external_api_token_service.py, 004_external_api_tokens.py |
| 2 | Bearer auth, schemas, error handlers, flask-smorest init | 4c02252 | api/__init__.py, auth.py, schemas.py, errors.py, app/__init__.py |

## Deviations from Plan

None - plan executed exactly as written.

## Threat Model Compliance

| Threat ID | Status | Implementation |
|-----------|--------|---------------|
| T-10-01 | Mitigated | require_api_token validates SHA-256 hash; 256-bit entropy via secrets.token_hex(32) |
| T-10-02 | Mitigated | Raw tokens never logged; only token_prefix (8 chars) used in log messages |
| T-10-03 | Mitigated | Error handlers return generic messages; logger.error with exc_info for internal correlation |
| T-10-05 | Mitigated | Only SHA-256 hash stored; raw token returned once at creation time |

## Verification Results

- Model import: OK
- Service import: OK
- flask-smorest 0.47.0: installed and importable
- All API module imports: OK (auth, schemas, errors, init_api)
- App creation: OK (REST API initialized log line confirmed)
- Swagger UI GET /api/v1/docs: 200
- OpenAPI spec GET /api/v1/openapi.json: 200

## Known Stubs

None - all contracts are fully implemented. Endpoints that use these schemas/auth will be added in Plan 02.

## Self-Check: PASSED

All 7 created files exist. Both commit hashes (782e67f, 4c02252) verified in git log.
