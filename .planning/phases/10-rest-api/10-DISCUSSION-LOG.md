# Phase 10: REST API - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 10-rest-api
**Areas discussed:** Token design, Response shape, Rate limiting strategy, OpenAPI docs approach

---

## Token Design

### Token format

| Option | Description | Selected |
|--------|-------------|----------|
| Opaque random strings | Server-generated random hex/base64 stored hashed in DB. Simple, revocable instantly, no crypto overhead. | ✓ |
| JWT with signing | Self-contained tokens with claims. Enables stateless validation but harder to revoke. | |
| You decide | Claude picks based on WhoDis architecture. | |

**User's choice:** Opaque random strings
**Notes:** None

### Token scoping

| Option | Description | Selected |
|--------|-------------|----------|
| All tokens get full read access | Any valid token can hit all read endpoints. Simpler model for small team. | |
| Per-token scopes | Admin assigns scopes at creation (search, profile, reports). More granular. | |
| You decide | Claude picks based on team context and requirements. | ✓ |

**User's choice:** You decide
**Notes:** Deferred to Claude's discretion for small team context.

### Token expiration

| Option | Description | Selected |
|--------|-------------|----------|
| Never expire (revoke only) | Tokens live until admin explicitly revokes. Simple for long-running integrations. | |
| Configurable TTL at creation | Admin sets expiration (30d, 90d, 1yr, never) when creating. | |
| You decide | Claude picks based on security vs. operational simplicity. | ✓ |

**User's choice:** You decide
**Notes:** Deferred to Claude's discretion.

### Token naming

| Option | Description | Selected |
|--------|-------------|----------|
| Required name/label | Admin must give each token a descriptive name. Makes audit logs meaningful. | ✓ |
| Optional description | Name is auto-generated, admin can optionally add a description. | |

**User's choice:** Required name/label
**Notes:** None

---

## Response Shape

### Envelope format

| Option | Description | Selected |
|--------|-------------|----------|
| Envelope with metadata | All responses wrapped: {"data": ..., "meta": {...}, "errors": [...]}. Consistent, extensible. | ✓ |
| Flat resource objects | Direct resource arrays. Simpler but harder to extend. | |
| You decide | Claude picks most pragmatic approach. | |

**User's choice:** Envelope with metadata
**Notes:** None

### Field depth

| Option | Description | Selected |
|--------|-------------|----------|
| Full profile (all sources) | Same merged result as web UI — AD, Graph, Genesys, M365 licenses. | ✓ |
| Core identity only | Subset: name, email, title, department, manager, phone, office. | |
| You decide | Claude determines appropriate field set. | |

**User's choice:** Full profile (all sources)
**Notes:** None

### Pagination

| Option | Description | Selected |
|--------|-------------|----------|
| Always paginated | Default page_size, cursor/offset params. Standard enterprise convention. | ✓ |
| Return all matches | No pagination for v1 — typically 1-5 matches. | |
| You decide | Claude picks based on result set sizes. | |

**User's choice:** Always paginated
**Notes:** None

### Error codes

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, include error codes | Machine-readable codes (TOKEN_EXPIRED, RATE_LIMITED) plus HTTP status. | ✓ |
| HTTP status only | Standard HTTP codes with human-readable message. | |
| You decide | Claude picks based on consumer needs. | |

**User's choice:** Yes, include error codes
**Notes:** None

---

## Rate Limiting Strategy

### Limit key

| Option | Description | Selected |
|--------|-------------|----------|
| Per-token limits | Each token has own rate bucket. One integration can't starve others. | ✓ |
| Global API limit | Single shared bucket for all API traffic. | |
| You decide | Claude picks based on API-05 requirement. | |

**User's choice:** Per-token limits
**Notes:** Matches API-05 requirement ("per-token limits").

### Threshold configuration

| Option | Description | Selected |
|--------|-------------|----------|
| Single default for all tokens | One global rate (e.g., 60 req/min) in encrypted config. | ✓ |
| Per-token configurable | Admin sets rate limit per token at creation. | |
| You decide | Claude picks for small team. | |

**User's choice:** Single default for all tokens
**Notes:** None

---

## OpenAPI Docs Approach

### Spec source

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-written YAML/JSON spec | Static file, no dependencies. Must be kept in sync manually. | |
| Auto-generated from code | Library generates spec from route decorators/schemas. Stays in sync. | ✓ |
| You decide | Claude picks lightest approach. | |

**User's choice:** Auto-generated from code
**Notes:** Researcher to determine best library fit (flask-smorest vs apispec).

### Docs viewer

| Option | Description | Selected |
|--------|-------------|----------|
| Swagger UI | Interactive API explorer with "Try it" feature. Industry standard. | ✓ |
| ReDoc | Clean read-only docs. No interactive testing. | |
| Raw JSON spec only | Just serve OpenAPI JSON. Consumers use own tools. | |

**User's choice:** Swagger UI
**Notes:** None

### Docs authentication

| Option | Description | Selected |
|--------|-------------|----------|
| Public (no auth) | Matches API-06: "accessible without authentication". | ✓ |
| Require auth | More secure but contradicts API-06. | |

**User's choice:** Public (no auth)
**Notes:** Per API-06 success criteria.

---

## Claude's Discretion

- Token scoping: whether all tokens get full read access or per-token permission scopes
- Token expiration policy: never-expire with revoke-only vs. configurable TTL
- Specific OpenAPI library choice: flask-smorest vs apispec (researcher determines)

## Deferred Ideas

None — discussion stayed within phase scope.
