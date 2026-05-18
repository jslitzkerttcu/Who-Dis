# Phase 10: REST API - Research

**Researched:** 2026-05-17
**Domain:** Flask REST API with token auth, rate limiting, OpenAPI docs
**Confidence:** HIGH

## Summary

Phase 10 delivers a read-only REST API (2 endpoints: search and profile) authenticated via opaque bearer tokens, rate-limited per-token, with auto-generated OpenAPI docs at `/api/v1/docs`. The existing codebase provides strong foundations: Flask-Limiter is already initialized with Redis-backed storage, SearchOrchestrator and ResultMerger handle the search logic, and the admin blueprint has established CRUD patterns for management UIs.

The primary technical decision is **flask-smorest** for OpenAPI spec generation and Swagger UI serving. It provides auto-generated specs from route decorators, built-in Swagger UI, and marshmallow-based request/response serialization -- all in one package. It integrates partially: only the new API blueprint uses flask-smorest's Blueprint class; all existing blueprints remain standard Flask blueprints unchanged.

**Primary recommendation:** Use flask-smorest 0.47.0 for the API blueprint (auto-spec + Swagger UI), a new `ExternalApiToken` model (separate from the internal `ApiToken`), and extend the existing Flask-Limiter with a custom `key_func` for per-token rate limiting.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Tokens are opaque random strings (hex/base64), stored hashed in the database. No JWT -- simple, instantly revocable, no crypto overhead.
- **D-02:** A NEW model is required for external API tokens -- the existing `ApiToken` model stores internal service tokens (Genesys, Graph) and is NOT suitable for this purpose.
- **D-03:** Admin must provide a required name/label when creating a token (e.g., "ServiceNow Integration", "Monitoring Script"). Makes audit logs and token list meaningful.
- **D-04:** All API responses use an envelope format: `{"data": ..., "meta": {...}, "errors": [...]}`. Consistent structure with built-in pagination metadata.
- **D-05:** Full profile data exposed -- API returns the same merged result as the web UI (AD fields, Graph data, Genesys status, M365 licenses).
- **D-06:** Search results are always paginated (default page_size, offset/cursor params in envelope `meta`).
- **D-07:** Error responses include machine-readable error codes: `{"error": {"code": "RATE_LIMITED", "message": "...", "details": {...}}}` alongside HTTP status codes.
- **D-08:** Rate limits are per-token -- each token has its own bucket via Flask-Limiter's custom key function.
- **D-09:** Single default rate threshold for all tokens (e.g., 60 req/min), stored in encrypted config. No per-token custom limits.
- **D-10:** OpenAPI spec is auto-generated from code using a library (flask-smorest or apispec -- researcher determines best fit).
- **D-11:** Swagger UI serves interactive docs at `/api/v1/docs` -- standard "Try it" explorer.
- **D-12:** Docs endpoint is publicly accessible (no authentication required), per API-06 success criteria.

### Claude's Discretion
- **D-02a:** Token scoping -- whether all tokens get full read access or per-token permission scopes. Consider the 4-5 person team context and API-01..06 requirements.
- **D-02b:** Token expiration policy -- never-expire with revoke-only vs. configurable TTL at creation. Balance security vs. operational simplicity for a small team.
- **D-10a:** Specific library choice between flask-smorest and apispec -- researcher determines best fit for the existing Flask blueprint architecture.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| API-01 | Admin can create and manage API tokens via admin UI | New `ExternalApiToken` model + admin blueprint token CRUD + UI-SPEC token management section |
| API-02 | External system can search users via `GET /api/v1/search?q=...` returning JSON | flask-smorest API blueprint + SearchOrchestrator reuse + envelope response schema |
| API-03 | External system can retrieve full user profile via `GET /api/v1/user/{email}` | flask-smorest API blueprint + ResultMerger reuse + profile response schema |
| API-04 | All API calls logged to audit trail with token identification | Extend `audit_service.log_search()` / `log_access()` with token_id + token_name context |
| API-05 | Rate limiting prevents abuse with configurable per-token limits | Flask-Limiter custom `key_func` returning token ID + config_get for threshold |
| API-06 | OpenAPI spec available at `/api/v1/docs` | flask-smorest `Api` object with `OPENAPI_SWAGGER_UI_PATH` config, unauthenticated |

</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Token CRUD (create/list/revoke) | API / Backend | Frontend Server (admin UI) | Token lifecycle is server-side; admin UI renders management forms |
| Bearer token authentication | API / Backend | -- | Token validation is purely server-side middleware |
| Search endpoint | API / Backend | -- | Reuses existing SearchOrchestrator service |
| Profile endpoint | API / Backend | -- | Reuses existing ResultMerger service |
| Rate limiting | API / Backend | -- | Flask-Limiter middleware, per-token key function |
| OpenAPI docs | CDN / Static | API / Backend | Swagger UI is a static JS bundle served by flask-smorest |
| Audit logging | API / Backend | Database / Storage | AuditLog model writes to PostgreSQL |
| Token storage | Database / Storage | -- | ExternalApiToken model in PostgreSQL |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| flask-smorest | 0.47.0 | OpenAPI spec generation + Swagger UI + request/response serialization | [ASSUMED] De facto standard for Flask REST APIs with auto-docs; wraps apispec + marshmallow + webargs into one coherent package. Maintained by marshmallow-code org. |
| marshmallow | 4.3.0 | Schema definition for request/response serialization | [ASSUMED] Auto-installed by flask-smorest; standard Python serialization/validation library |
| webargs | 8.7.1 | Request argument parsing | [ASSUMED] Auto-installed by flask-smorest; handles query params and JSON body parsing |
| apispec | 6.10.0 | OpenAPI spec core | [ASSUMED] Auto-installed by flask-smorest; generates OpenAPI 3.x specs |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Flask-Limiter | >=3.5,<4 | Rate limiting | Per-token rate limiting via custom key_func on API routes |
| Flask | 3.1.3 | Web framework | API blueprint registration, request handling |
| SQLAlchemy | 2.0.45 | ORM | ExternalApiToken model, database operations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| flask-smorest | apispec + apispec-webframeworks | Lower-level; requires manual Swagger UI setup, manual route-to-spec registration, no request/response serialization. More work for same result. |
| flask-smorest | Static OpenAPI YAML file | Zero dependencies but no auto-generation; spec drifts from code. Only 2 endpoints makes this feasible but fragile. |
| flask-smorest | flask-apispec | Older, less maintained. Last release 0.7.0 in 2020. Not recommended. |
| marshmallow schemas | Manual dict construction | No validation, no auto-docs, envelope format requires boilerplate in every route. |

**Installation:**
```bash
pip install flask-smorest==0.47.0
```
This pulls in marshmallow 4.3.0, webargs 8.7.1, apispec 6.10.0 as dependencies.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| flask-smorest | PyPI | 6+ yrs | Established | github.com/marshmallow-code/flask-smorest | [OK] | Approved |
| marshmallow | PyPI | 10+ yrs | Very high | github.com/marshmallow-code/marshmallow | [OK] | Approved |
| webargs | PyPI | 9+ yrs | High | github.com/marshmallow-code/webargs | [OK] | Approved |
| apispec | PyPI | 9+ yrs | High | github.com/marshmallow-code/apispec | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*All packages passed slopcheck verification. All are part of the marshmallow-code GitHub organization -- a well-established open-source ecosystem.*

## Architecture Patterns

### System Architecture Diagram

```
External Client                  Admin User (Browser)
      |                                |
      | Bearer Token                   | OIDC Session
      | Authorization: Bearer <token>  | @require_role("admin")
      v                                v
 +----+----------+          +----------+---------+
 | API Blueprint  |          | Admin Blueprint     |
 | /api/v1/...   |          | /admin/api-tokens/* |
 +----+----------+          +----------+---------+
      |                                |
      | validate_api_token()           | CRUD operations
      v                                v
 +----+----------+          +----------+---------+
 | Token Auth     |          | ExternalApiToken   |
 | Middleware     |          | Model              |
 +-------+-------+          +----------+---------+
         |                             |
         | g.api_token = token         |
         v                             |
 +-------+-------+                    |
 | Flask-Limiter  |                    |
 | key: token.id  |                    |
 +-------+-------+                    |
         |                             |
         v                             |
 +-------+-----------------------+     |
 | SearchOrchestrator            |     |
 | ResultMerger                  |     |
 | (reused from web UI)          |     |
 +-------+-----------------------+     |
         |                             |
         v                             v
 +-------+-------+          +---------+--------+
 | AuditLog       |          | PostgreSQL       |
 | (token_id ctx)  |          | external_api_    |
 +----------------+          | tokens table     |
                             +-----------------+

 Swagger UI (public)
 /api/v1/docs  -->  flask-smorest serves static JS bundle
```

### Recommended Project Structure
```
app/
├── blueprints/
│   ├── api/                    # NEW: REST API blueprint
│   │   ├── __init__.py         # flask-smorest Blueprint + Api registration
│   │   ├── auth.py             # Bearer token validation decorator
│   │   ├── schemas.py          # Marshmallow schemas (envelope, search, profile, error)
│   │   ├── search.py           # GET /api/v1/search endpoint
│   │   ├── users.py            # GET /api/v1/user/{email} endpoint
│   │   └── errors.py           # API-specific error handlers (JSON envelope)
│   └── admin/
│       ├── __init__.py         # (existing) -- add token management routes
│       └── api_tokens.py       # NEW: Token CRUD routes for admin UI
├── models/
│   └── external_api_token.py   # NEW: ExternalApiToken model
├── services/
│   └── external_api_token_service.py  # NEW: Token service (hash, validate, CRUD)
└── templates/
    └── admin/
        ├── _external_api_tokens.html    # Token management section
        ├── _token_create_modal.html     # Create modal
        ├── _token_reveal_modal.html     # One-time reveal modal
        └── _token_revoke_modal.html     # Revoke confirmation modal
```

### Pattern 1: flask-smorest Partial Integration
**What:** Only the API blueprint uses flask-smorest's Blueprint class. All existing blueprints remain standard Flask blueprints.
**When to use:** When adding API docs to a subset of routes in an existing Flask app.
**Example:**
```python
# app/blueprints/api/__init__.py
# Source: flask-smorest docs (https://flask-smorest.readthedocs.io/en/latest/quickstart.html) [ASSUMED]
from flask_smorest import Api, Blueprint as ApiBlueprint

api_bp = ApiBlueprint("api_v1", __name__, url_prefix="/api/v1",
                       description="WhoDis REST API v1")

def init_api(app):
    """Initialize flask-smorest Api and register API blueprint."""
    app.config.update({
        "API_TITLE": "WhoDis API",
        "API_VERSION": "v1",
        "OPENAPI_VERSION": "3.0.3",
        "OPENAPI_URL_PREFIX": "/api/v1",
        "OPENAPI_SWAGGER_UI_PATH": "/docs",
        "OPENAPI_SWAGGER_UI_URL": "https://cdn.jsdelivr.net/npm/swagger-ui-dist/",
    })
    api = Api(app)
    api.register_blueprint(api_bp)
    return api
```

### Pattern 2: Bearer Token Auth Decorator
**What:** Custom decorator that validates opaque bearer tokens against the database, sets `g.api_token` for downstream use.
**When to use:** All API routes except `/api/v1/docs`.
**Example:**
```python
# app/blueprints/api/auth.py
import hashlib
import secrets
from functools import wraps
from flask import request, g, jsonify

def require_api_token(f):
    """Validate bearer token and set g.api_token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": {"code": "MISSING_TOKEN",
                "message": "Authorization header with Bearer token required"}}), 401

        raw_token = auth_header[7:]  # Strip "Bearer "
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        from app.models.external_api_token import ExternalApiToken
        token = ExternalApiToken.query.filter_by(
            token_hash=token_hash, is_revoked=False
        ).first()

        if not token:
            return jsonify({"error": {"code": "INVALID_TOKEN",
                "message": "Invalid or revoked API token"}}), 401

        # Update last_used timestamp
        token.record_usage()
        g.api_token = token
        g.user = f"api:{token.name}"  # For audit trail compatibility
        return f(*args, **kwargs)
    return decorated
```

### Pattern 3: ExternalApiToken Model
**What:** New model separate from existing `ApiToken`. Stores hashed tokens with metadata.
**When to use:** D-02 mandates a new model.
**Example:**
```python
# app/models/external_api_token.py
import hashlib
import secrets
from datetime import datetime, timezone
from app.database import db
from app.models.base import BaseModel, TimestampMixin

class ExternalApiToken(BaseModel, TimestampMixin):
    __tablename__ = "external_api_tokens"

    name = db.Column(db.String(100), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    token_prefix = db.Column(db.String(8), nullable=False)  # First 8 chars for identification
    created_by = db.Column(db.String(255), nullable=False)  # Admin email
    is_revoked = db.Column(db.Boolean, default=False, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True))
    revoked_by = db.Column(db.String(255))
    last_used_at = db.Column(db.DateTime(timezone=True))
    usage_count = db.Column(db.Integer, default=0, nullable=False)

    @classmethod
    def create_token(cls, name: str, created_by: str):
        """Generate and store a new token. Returns (model, raw_token)."""
        raw_token = secrets.token_hex(32)  # 64-char hex string
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token = cls(
            name=name,
            token_hash=token_hash,
            token_prefix=raw_token[:8],
            created_by=created_by,
        )
        token.save()
        return token, raw_token  # raw_token shown once, never stored

    def revoke(self, revoked_by: str):
        self.update(is_revoked=True,
                    revoked_at=datetime.now(timezone.utc),
                    revoked_by=revoked_by)

    def record_usage(self):
        self.last_used_at = datetime.now(timezone.utc)
        self.usage_count += 1
        db.session.commit()
```

### Pattern 4: Per-Token Rate Limiting
**What:** Custom key function for Flask-Limiter that uses the token ID from `g.api_token`.
**When to use:** D-08 requires per-token rate buckets.
**Example:**
```python
# In API blueprint routes
from app import limiter

def _api_token_rate_key():
    """Rate limit key: use token ID for per-token buckets."""
    token = getattr(g, "api_token", None)
    if token:
        return f"api_token:{token.id}"
    return get_remote_address()  # Fallback for unauthenticated

# Usage on route:
@api_bp.route("/search")
@require_api_token
@limiter.limit("60/minute", key_func=_api_token_rate_key)
def search():
    ...
```

### Pattern 5: Envelope Response with Marshmallow
**What:** Consistent response envelope per D-04.
**Example:**
```python
# app/blueprints/api/schemas.py
import marshmallow as ma

class MetaSchema(ma.Schema):
    page = ma.fields.Integer()
    page_size = ma.fields.Integer()
    total = ma.fields.Integer()

class ErrorSchema(ma.Schema):
    code = ma.fields.String(required=True)
    message = ma.fields.String(required=True)
    details = ma.fields.Dict()

class SearchResultSchema(ma.Schema):
    email = ma.fields.String()
    display_name = ma.fields.String()
    department = ma.fields.String()
    title = ma.fields.String()
    source = ma.fields.String()

class SearchResponseSchema(ma.Schema):
    data = ma.fields.List(ma.fields.Nested(SearchResultSchema))
    meta = ma.fields.Nested(MetaSchema)
    errors = ma.fields.List(ma.fields.Nested(ErrorSchema), load_default=None)
```

### Anti-Patterns to Avoid
- **Reusing existing `ApiToken` model:** D-02 explicitly forbids this. The existing model stores internal service tokens (Genesys/Graph) with different semantics (refresh tokens, service_name, etc.).
- **JWT tokens:** D-01 explicitly chose opaque tokens for instant revocability without crypto overhead.
- **Duplicating SearchOrchestrator logic in API routes:** Reuse the existing orchestrator; just wrap its output in the envelope format.
- **Registering all blueprints with flask-smorest Api:** Only the API blueprint goes through `api.register_blueprint()`. Existing blueprints stay as `app.register_blueprint()`.
- **Storing raw tokens in the database:** Only store the SHA-256 hash. The raw token is shown once at creation (like GitHub PATs).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenAPI spec generation | Manual YAML/JSON spec file | flask-smorest auto-generation | Spec drifts from code; manual maintenance burden for even 2 endpoints |
| Swagger UI hosting | Custom HTML page with embedded swagger-ui.js | flask-smorest built-in Swagger UI | CDN-backed, auto-configured, zero maintenance |
| Request validation | Manual `request.args.get()` + type checking | marshmallow schemas via flask-smorest `@arguments` | Consistent validation, auto-documented in OpenAPI spec |
| Response serialization | Manual `jsonify()` with ad-hoc dicts | marshmallow schemas via flask-smorest `@response` | Consistent envelope, auto-documented response shapes |
| Token hashing | Custom hash implementation | `hashlib.sha256` (stdlib) | Standard, no dependencies, well-understood |
| Token generation | Custom random string | `secrets.token_hex(32)` (stdlib) | Cryptographically secure, standard library |

**Key insight:** flask-smorest solves the "spec-from-code" problem, the "Swagger UI hosting" problem, and the "request/response validation" problem in one package. Using apispec alone would require solving each separately.

## Common Pitfalls

### Pitfall 1: OPTIONS Requests Blocked by Global before_request
**What goes wrong:** The global `before_request` in `app/__init__.py` (line 287-289) returns 405 for all OPTIONS requests. Swagger UI's "Try it" and external CORS preflight requests use OPTIONS.
**Why it happens:** The block was added before the API existed. Same-origin Swagger UI requests won't trigger CORS preflight, but external API clients from browsers will.
**How to avoid:** For Phase 10 (read-only API, server-to-server), this is acceptable -- external clients are scripts/services, not browsers. Document that CORS support is a v2 concern if browser-based clients are needed later.
**Warning signs:** Swagger UI "Try it" works (same origin) but external browser-based JS clients get 405 on preflight.

### Pitfall 2: Rate Limiter Decorator Order
**What goes wrong:** If `@limiter.limit()` runs BEFORE `@require_api_token`, `g.api_token` is not yet set, so the custom key function falls back to IP-based limiting instead of per-token.
**Why it happens:** Flask decorators execute bottom-up (closest to function first). The auth decorator must run first (closest to function) to populate `g.api_token`.
**How to avoid:** Decorator order must be: `@api_bp.route()` -> `@limiter.limit()` -> `@require_api_token` -> function. This means `@require_api_token` is the INNERMOST decorator.
**Warning signs:** All API calls from different tokens sharing the same rate limit bucket.

### Pitfall 3: Token Hash Timing Attack
**What goes wrong:** String comparison of token hash using `==` leaks timing information that could theoretically allow hash reconstruction.
**Why it happens:** Standard string comparison short-circuits on first mismatched character.
**How to avoid:** Use `hmac.compare_digest()` for hash comparison. However, since we're querying the database by hash (not comparing in Python), the database query itself is not timing-safe but the attack vector is negligible for a 4-5 person team with hashed tokens. Note for awareness but don't over-engineer.
**Warning signs:** N/A -- theoretical risk, not practical for this deployment.

### Pitfall 4: SearchOrchestrator Request Context in API
**What goes wrong:** SearchOrchestrator uses `copy_current_request_context` for ThreadPoolExecutor. The API route must ensure `g.user` and request context are properly set for the orchestrator to work.
**Why it happens:** The orchestrator was designed for the web UI where `g.user` is set by OIDC auth. The API auth decorator sets `g.user` differently (to `api:{token_name}`).
**How to avoid:** The `require_api_token` decorator must set `g.user` before the orchestrator runs. Format: `g.user = f"api:{token.name}"` for audit trail traceability.
**Warning signs:** SearchOrchestrator errors about missing user context or audit entries without user attribution.

### Pitfall 5: flask-smorest Api Initialization Order
**What goes wrong:** flask-smorest's `Api(app)` must be called AFTER all app config is set but BEFORE blueprint registration. If called too early, config values are missing; too late, blueprints aren't documented.
**Why it happens:** flask-smorest reads `API_TITLE`, `OPENAPI_VERSION`, etc. from `app.config` at `Api(app)` time.
**How to avoid:** Initialize the Api object in `create_app()` after all config is set, before/during blueprint registration. Use `init_api(app)` function pattern.
**Warning signs:** Missing API title in Swagger UI, or blueprints not showing up in docs.

### Pitfall 6: Envelope Format Inconsistency Between Success and Error
**What goes wrong:** Success responses use `{"data": ..., "meta": ..., "errors": null}` but error responses might use plain `{"error": {...}}` from Flask error handlers, creating inconsistency.
**Why it happens:** Flask's default error handlers return different shapes than flask-smorest decorated routes.
**How to avoid:** Register custom error handlers on the API blueprint that format ALL errors (400, 401, 403, 404, 429, 500) in the D-07 format: `{"error": {"code": "...", "message": "...", "details": {...}}}`.
**Warning signs:** API clients receiving different JSON shapes for errors vs. successes.

## Code Examples

### flask-smorest API Blueprint with Existing Flask App
```python
# Source: flask-smorest quickstart docs [ASSUMED]
# app/__init__.py (additions to create_app)
from app.blueprints.api import init_api

def create_app():
    app = Flask(__name__)
    # ... existing setup ...

    # Initialize REST API (flask-smorest) -- after all config, before return
    init_api(app)

    return app
```

### Search Endpoint with Envelope Response
```python
# Source: project patterns + flask-smorest docs [ASSUMED]
# app/blueprints/api/search.py
from flask.views import MethodView
from flask_smorest import Blueprint as ApiBlueprint
from app.blueprints.api.auth import require_api_token
from app.blueprints.api.schemas import SearchResponseSchema, SearchQuerySchema
from app import limiter

api_bp = ApiBlueprint("api_v1_search", __name__)

def _api_token_rate_key():
    from flask import g
    token = getattr(g, "api_token", None)
    return f"api_token:{token.id}" if token else "anonymous"

@api_bp.route("/search")
class SearchResource(MethodView):
    @require_api_token
    @limiter.limit("60/minute", key_func=_api_token_rate_key)
    @api_bp.arguments(SearchQuerySchema, location="query")
    @api_bp.response(200, SearchResponseSchema)
    def get(self, args):
        """Search users across identity providers."""
        query = args["q"]
        page = args.get("page", 1)
        page_size = args.get("page_size", 25)

        orchestrator = SearchOrchestrator()
        # ... reuse existing search logic ...
        return {"data": results, "meta": {"page": page, "page_size": page_size, "total": total}}
```

### Admin Token Management Route
```python
# Source: project patterns (admin blueprint conventions) [ASSUMED]
# app/blueprints/admin/api_tokens.py
from flask import Blueprint, request, jsonify, g
from app.middleware.auth import require_role
from app.utils.error_handler import handle_errors
from app.models.external_api_token import ExternalApiToken

@admin_bp.route("/api-tokens/create", methods=["POST"])
@require_role("admin")
@handle_errors(json_response=True)
def create_api_token():
    """Create a new external API token."""
    name = request.form.get("name", "").strip()
    if not name or len(name) < 2:
        return jsonify({"error": "Token name must be at least 2 characters"}), 400

    token_model, raw_token = ExternalApiToken.create_token(
        name=name, created_by=g.user
    )

    # Audit log
    audit_service = current_app.container.get("audit_logger")
    audit_service.log_admin_action(
        user_email=g.user,
        action="api_token_created",
        target=token_model.name,
        details={"token_id": token_model.id, "token_prefix": token_model.token_prefix}
    )

    # Return raw token via HX-Trigger for one-time reveal
    response = jsonify({"success": True, "token_id": token_model.id})
    response.headers["HX-Trigger"] = json.dumps({
        "tokenCreated": {"token": raw_token, "name": name}
    })
    return response
```

### Alembic Migration for ExternalApiToken
```python
# Source: project patterns (alembic migration conventions) [ASSUMED]
# alembic/versions/xxx_add_external_api_tokens.py
def upgrade():
    op.create_table(
        "external_api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("token_prefix", sa.String(8), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), default=False, nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by", sa.String(255)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("usage_count", sa.Integer(), default=0, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_external_api_tokens_token_hash", "external_api_tokens", ["token_hash"])
    op.create_index("ix_external_api_tokens_is_revoked", "external_api_tokens", ["is_revoked"])
```

## Discretion Recommendations

### D-02a: Token Scoping
**Recommendation:** All tokens get full read access. No per-token permission scopes.

**Rationale:** The API exposes exactly 2 read-only endpoints (search, profile). For a 4-5 person team, per-token scopes add implementation complexity (scope model, scope validation middleware, scope documentation) with zero practical benefit -- every token would need both scopes anyway. If write endpoints are added in v2, scoping can be introduced then. [ASSUMED]

### D-02b: Token Expiration Policy
**Recommendation:** Never-expire with revoke-only. No configurable TTL.

**Rationale:** For a small IT team creating tokens for known internal integrations (ServiceNow, monitoring scripts), forced expiration creates operational toil (tokens silently stop working, require admin intervention to rotate). Revocation is instant (D-01) and sufficient for security. The admin UI shows last-used timestamps, making it easy to spot unused tokens for cleanup. Add optional TTL in v2 if the team grows or external partners get tokens. [ASSUMED]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flask-RESTful | flask-smorest | ~2020 | flask-smorest integrates with marshmallow ecosystem; Flask-RESTful is less actively maintained |
| apispec manual setup | flask-smorest wrapping apispec | Ongoing | flask-smorest automates what apispec requires manually |
| Swagger 2.0 | OpenAPI 3.0.3 | ~2017 | Modern spec format; flask-smorest defaults to OAS 3.x |
| Flask-Limiter 2.x | Flask-Limiter 3.x/4.x | 2022 | Breaking changes in storage backend config; project already on >=3.5 |

**Deprecated/outdated:**
- **Flask-RESTful:** Less actively maintained; flask-smorest is the modern choice for Flask REST APIs with auto-docs
- **flask-apispec:** Last release 2020; unmaintained
- **Swagger 2.0 spec:** Superseded by OpenAPI 3.0.x/3.1.x

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | flask-smorest 0.47.0 supports partial integration (only API blueprint registered with Api object) | Standard Stack | HIGH -- if flask-smorest requires ALL blueprints to use its Blueprint class, architecture approach breaks. Mitigation: the official docs describe `api.register_blueprint()` for specific blueprints, and existing blueprints use standard `app.register_blueprint()`. |
| A2 | flask-smorest serves Swagger UI from CDN without bundling static files | Architecture Patterns | LOW -- if CDN approach doesn't work, can bundle swagger-ui-dist locally. |
| A3 | marshmallow 4.x is compatible with flask-smorest 0.47.0 | Standard Stack | MEDIUM -- flask-smorest 0.47.0 specifies `marshmallow<5,>=3.24.1` so 4.3.0 is in range. |
| A4 | All tokens should get full read access (no scoping) | Discretion D-02a | LOW -- if user wants scoping, it can be added later without breaking the token model. |
| A5 | Never-expire tokens are acceptable for this team size | Discretion D-02b | LOW -- if user wants TTL, adding an optional expires_at column is backward-compatible. |
| A6 | Flask-Limiter's per-route `key_func` override works with flask-smorest's MethodView pattern | Architecture Patterns | MEDIUM -- if `@limiter.limit()` doesn't compose with flask-smorest decorators, may need to apply limiting differently (e.g., `before_request` hook on API blueprint). |

## Open Questions

1. **flask-smorest MethodView vs. function-based views**
   - What we know: flask-smorest supports both MethodView classes and function-based views for route definitions.
   - What's unclear: Which pattern integrates more cleanly with the existing project conventions (function-based routes are used everywhere else).
   - Recommendation: Use MethodView for API routes (flask-smorest's recommended pattern) since the API blueprint is isolated from existing code.

2. **Profile photo handling in API response**
   - What we know: D-05 says full profile data. Profile photos are binary blobs (base64-encoded in web UI).
   - What's unclear: Should the API return base64-encoded photo data in the JSON response, or a URL to a photo endpoint?
   - Recommendation: Return a photo URL (`/api/v1/user/{email}/photo`) rather than embedding base64 in every profile response. Keeps response size manageable.

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Flask/PostgreSQL/HTMX -- extend existing patterns, don't introduce new frameworks. flask-smorest is a Flask extension, not a new framework.
- **Auth:** Azure AD SSO / Keycloak OIDC for web UI; API tokens for REST API (bypasses SSO by design).
- **Security:** All write operations require audit trail. Token creation/revocation are admin actions logged to audit.
- **DI Container:** New services registered in `app/container.py`. ExternalApiToken service must be registered.
- **Decorators:** `@auth_required` and `@require_role()` on admin token management routes. API routes use custom `@require_api_token` instead.
- **Error handling:** `@handle_errors` / `@handle_service_errors` patterns. API routes need JSON-only error responses.
- **Model patterns:** Extend `BaseModel` + `TimestampMixin`. Follow naming conventions.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured) |
| Config file | `tests/conftest.py` (session-scoped testcontainers Postgres) |
| Quick run command | `pytest tests/unit/ -x -q` |
| Full suite command | `pytest tests/ -v --cov=app` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-01 | Admin creates/revokes tokens | unit + integration | `pytest tests/unit/services/test_external_api_token_service.py -x` | No -- Wave 0 |
| API-02 | GET /api/v1/search returns JSON | integration | `pytest tests/integration/test_api_search.py -x` | No -- Wave 0 |
| API-03 | GET /api/v1/user/{email} returns profile | integration | `pytest tests/integration/test_api_profile.py -x` | No -- Wave 0 |
| API-04 | API calls logged with token ID | integration | `pytest tests/integration/test_api_audit.py -x` | No -- Wave 0 |
| API-05 | Rate limiting per token | integration | `pytest tests/integration/test_api_rate_limit.py -x` | No -- Wave 0 |
| API-06 | /api/v1/docs accessible without auth | integration | `pytest tests/integration/test_api_docs.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/ -x -q`
- **Per wave merge:** `pytest tests/ -v --cov=app`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/services/test_external_api_token_service.py` -- covers API-01 (token CRUD)
- [ ] `tests/unit/models/test_external_api_token.py` -- covers token model (hash, revoke, usage)
- [ ] `tests/integration/test_api_endpoints.py` -- covers API-02, API-03, API-04, API-06
- [ ] `tests/integration/test_api_rate_limit.py` -- covers API-05
- [ ] `tests/fakes/fake_api_token.py` -- test fixtures for ExternalApiToken

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Bearer token validation via SHA-256 hash lookup; `require_api_token` decorator |
| V3 Session Management | no | API is stateless; no sessions. Token revocation is the session-equivalent |
| V4 Access Control | yes | All tokens get read-only access; admin-only token management via `@require_role("admin")` |
| V5 Input Validation | yes | marshmallow schemas validate all query parameters and path params |
| V6 Cryptography | yes | `secrets.token_hex(32)` for generation; `hashlib.sha256` for hashing; tokens never stored raw |

### Known Threat Patterns for Flask REST API

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token theft via logs | Information Disclosure | Never log raw tokens; log only token_prefix (first 8 chars) or token_id |
| Brute-force token guessing | Spoofing | 64-hex-char tokens (256-bit entropy); rate limiting on failed auth |
| Rate limit bypass via IP rotation | Denial of Service | Per-token limiting (D-08) not per-IP; token ID is the bucket key |
| Enum attack on /api/v1/user/{email} | Information Disclosure | Valid token required; audit log all lookups; consider returning 404 for non-existent users (not 403) |
| Token stored in browser history | Information Disclosure | Token only shown once in admin UI modal; never in URL params |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `app/__init__.py`, `app/container.py`, `app/models/api_token.py`, `app/middleware/auth.py`, `app/blueprints/search/__init__.py` -- verified existing patterns, Flask-Limiter initialization, decorator order conventions
- PyPI registry: flask-smorest 0.47.0, marshmallow 4.3.0, webargs 8.7.1, apispec 6.10.0 -- versions verified via `pip index versions`
- slopcheck: All 4 packages passed [OK]
- flask-smorest official docs: https://flask-smorest.readthedocs.io/en/latest/ -- Swagger UI config, Blueprint class, partial integration

### Secondary (MEDIUM confidence)
- Flask-Limiter docs: https://flask-limiter.readthedocs.io/en/stable/recipes.html -- custom key_func per-route pattern
- flask-smorest quickstart: https://flask-smorest.readthedocs.io/en/latest/quickstart.html -- Api initialization pattern

### Tertiary (LOW confidence)
- Training data on flask-smorest partial integration with existing Flask apps -- marked [ASSUMED] in Assumptions Log

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- flask-smorest is well-established, versions verified, slopcheck clean
- Architecture: HIGH -- patterns derived from existing codebase inspection + official docs
- Pitfalls: HIGH -- identified from codebase analysis (OPTIONS blocking, decorator order, rate limiter key)

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (stable ecosystem, monthly cadence sufficient)
