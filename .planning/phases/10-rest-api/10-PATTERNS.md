# Phase 10: REST API - Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 13 new/modified files
**Analogs found:** 12 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/blueprints/api/__init__.py` | config/route | request-response | `app/blueprints/admin/__init__.py` | role-match |
| `app/blueprints/api/auth.py` | middleware | request-response | `app/middleware/auth.py` | exact |
| `app/blueprints/api/schemas.py` | utility | transform | None (new library: marshmallow) | no-analog |
| `app/blueprints/api/search.py` | controller | request-response | `app/blueprints/search/__init__.py` | role-match |
| `app/blueprints/api/users.py` | controller | request-response | `app/blueprints/search/__init__.py` | role-match |
| `app/blueprints/api/errors.py` | middleware | request-response | `app/utils/error_handler.py` | role-match |
| `app/blueprints/admin/api_tokens.py` | controller | CRUD | `app/blueprints/admin/users.py` | exact |
| `app/models/external_api_token.py` | model | CRUD | `app/models/user.py` | exact |
| `app/services/external_api_token_service.py` | service | CRUD | `app/services/audit_service_postgres.py` | role-match |
| `app/__init__.py` (modify) | config | -- | self | exact |
| `app/container.py` (modify) | config | -- | self | exact |
| `database/create_database.sql` (modify) | migration | -- | self | exact |
| `app/templates/admin/_external_api_tokens.html` | component | -- | `app/templates/admin/_api_tokens.html` | exact |

## Pattern Assignments

### `app/models/external_api_token.py` (model, CRUD)

**Analog:** `app/models/user.py`

**Imports pattern** (lines 1-8):
```python
from datetime import datetime, timezone
from typing import Optional, List
from app.database import db
from app.models.base import BaseModel, TimestampMixin
```

**Model declaration pattern** (lines 10-25):
```python
class User(BaseModel, TimestampMixin):
    """Enhanced user model with proper relationships."""

    __tablename__ = "users"

    # Role constants
    ROLE_VIEWER = "viewer"
    ROLE_EDITOR = "editor"
    ROLE_ADMIN = "admin"

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    role = db.Column(db.String(50), nullable=False, default=ROLE_VIEWER, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
```

**Class method pattern** (lines 41-52):
```python
@classmethod
def get_by_email(cls, email: str) -> Optional["User"]:
    """Get user by email address."""
    return cls.query.filter_by(email=email.lower().strip()).first()

@classmethod
def get_by_role(cls, role: str, active_only: bool = True) -> List["User"]:
    """Get all users with specific role."""
    query = cls.query.filter_by(role=role)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.all()
```

**Key patterns:** Extend `BaseModel, TimestampMixin`. Use `db.Column` with `index=True` on query fields. Use `save()` / `update()` from BaseModel. Classmethod for queries.

---

### `app/blueprints/admin/api_tokens.py` (controller, CRUD)

**Analog:** `app/blueprints/admin/users.py`

**Imports pattern** (lines 1-11):
```python
from flask import render_template, request, jsonify, g
from app.middleware.auth import require_role
from app.database import db
from app.models import User, UserNote
from app.services.audit_service_postgres import audit_service
from app.utils.timezone import format_timestamp
```

**Auth + CRUD route pattern** (lines 46-80):
```python
@require_role("admin")
def add_user():
    """Add a new user."""
    data = request.get_json()
    email = data.get("email", "").lower()
    role = data.get("role", "viewer")

    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "User already exists"}), 409

    # Add user
    admin_email = g.user or "unknown"
    user = User(email=email, role=role, created_by=admin_email)
    db.session.add(user)
    db.session.commit()

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="add_user",
        target=f"user:{email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"user": email, "role": role},
    )

    return jsonify({"success": True, "message": "User added successfully"})
```

**Route registration pattern** (`app/blueprints/admin/__init__.py` lines 30-34):
```python
admin_bp.route("/users", endpoint="users")(users.manage_users)
admin_bp.route("/api/users")(users.api_users)
admin_bp.route("/users/add", methods=["POST"])(users.add_user)
admin_bp.route("/users/update", methods=["POST"])(users.update_user)
admin_bp.route("/users/delete", methods=["POST"])(users.delete_user)
```

---

### `app/blueprints/api/__init__.py` (config/route, request-response)

**Analog:** `app/blueprints/admin/__init__.py` + `app/__init__.py` lines 298-320

**Blueprint creation pattern** (`app/blueprints/admin/__init__.py` lines 1-20):
```python
from flask import Blueprint, render_template, request, jsonify, render_template_string
from app.middleware.auth import require_role

admin_bp = Blueprint("admin", __name__)
```

**Blueprint registration pattern** (`app/__init__.py` lines 298-320):
```python
from app.blueprints.admin import admin_bp
app.register_blueprint(admin_bp, url_prefix="/admin")

from app.blueprints.admin.jobs import jobs_api_bp
app.register_blueprint(jobs_api_bp, url_prefix="/api/v2/admin/jobs")
```

**Separate API blueprint pattern** (`app/blueprints/admin/jobs.py` lines 14-20):
```python
from flask import Blueprint, current_app, g, jsonify, request

jobs_api_bp = Blueprint("jobs_api", __name__)
```

**Note:** The API blueprint will use flask-smorest's `Blueprint` instead of Flask's standard `Blueprint`. Only this blueprint is registered with `Api()`. All existing blueprints remain unchanged.

---

### `app/blueprints/api/auth.py` (middleware, request-response)

**Analog:** `app/middleware/auth.py`

**Decorator pattern** (lines 97-128):
```python
def auth_required(f):
    """Decorator to require authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not authenticate():
            if not hasattr(g, "user") or g.user is None:
                log_access_denied()
                # ... handle response ...
                return redirect(url_for("home.login", reason="auth_required"))
            else:
                return render_template("nope.html", ...), 401
        request.user_role = g.role
        return f(*args, **kwargs)

    return decorated_function
```

**JSON-returning auth decorator pattern** (lines 182-191):
```python
def login_required(f):
    """Simple decorator to check if user is logged in (for API endpoints)"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not authenticate():
            return {"error": "Authentication required"}, 401
        return f(*args, **kwargs)

    return decorated_function
```

**Key difference:** API auth uses bearer token validation (hash lookup) instead of OIDC. Returns JSON error envelope per D-07. Sets `g.api_token` and `g.user = f"api:{token.name}"`.

---

### `app/blueprints/api/search.py` (controller, request-response)

**Analog:** `app/blueprints/search/__init__.py`

**Search orchestration pattern** (lines 1274-1353):
```python
@search_bp.route("/search", methods=["POST"])
@limiter.limit("30/minute", key_func=_search_rate_key)
@require_role("viewer")
@handle_errors
def search():
    """Search endpoint that returns HTML for Htmx."""
    search_term = request.form.get("query", "").strip()

    if not search_term:
        return '<div class="text-center text-gray-500 py-8">Please enter a search term</div>'

    # Initialize services
    orchestrator = SearchOrchestrator()
    merger = ResultMerger()

    # Execute concurrent searches
    ldap_result, genesys_result, graph_result = orchestrator.execute_concurrent_search(
        search_term
    )

    # Merge results
    azure_ad_result, azure_ad_error, azure_ad_multiple = merger.merge_azure_ad_results(
        ldap_result, genesys_result, graph_result
    )
```

**Rate limiting key function pattern** (lines 35-43):
```python
def _search_rate_key() -> str:
    """SEC-03 rate-limit key: prefer authenticated user, fall back to remote IP."""
    return getattr(g, "user", None) or get_remote_address()
```

**Key difference:** API endpoint returns JSON envelope instead of HTML. Uses `@require_api_token` instead of `@require_role`. Rate limit key uses `g.api_token.id`.

---

### `app/blueprints/api/errors.py` (middleware, request-response)

**Analog:** `app/utils/error_handler.py`

**Error handler decorator pattern** (lines 12-158):
```python
def handle_errors(
    func: Optional[Callable] = None,
    *,
    json_response: bool = False,
    ...
) -> Callable:

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return f(*args, **kwargs)
            except Exception as e:
                # ...
                if isinstance(e, ValueError):
                    status_code = 400
                elif isinstance(e, PermissionError):
                    status_code = 403
                elif isinstance(e, FileNotFoundError):
                    status_code = 404
                elif isinstance(e, SQLAlchemyError):
                    error_message = "Database error occurred"

                if json_response:
                    return jsonify({
                        "error": error_message,
                        "error_type": type(e).__name__,
                        "error_id": error_id,
                        "status": "error",
                    }), status_code
```

**Key difference:** API errors use D-07 envelope: `{"error": {"code": "ERROR_CODE", "message": "...", "details": {...}}}`. Must handle 401 (INVALID_TOKEN), 429 (RATE_LIMITED), and Flask-Limiter's automatic 429 responses.

---

### `app/services/external_api_token_service.py` (service, CRUD)

**Analog:** `app/services/audit_service_postgres.py`

**Service initialization pattern** (lines 1-17):
```python
import logging
from typing import Optional, Dict, Any, List
from app.database import db

logger = logging.getLogger(__name__)


class PostgresAuditService(IAuditLogger, IAuditQueryService):
    """PostgreSQL-based audit service using SQLAlchemy models"""

    def __init__(self):
        logger.info("PostgreSQL audit service initialized")
```

**Error-swallowing pattern for non-critical operations** (lines 25-42):
```python
def log_search(self, user_email: str, search_query: str, ...):
    try:
        AuditLog.log_search(user_email, search_query, results_count, services, **kwargs)
    except Exception as e:
        logger.error(f"Failed to log search: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
```

**Container registration pattern** (`app/container.py` lines 139-141):
```python
audit_service_instance = PostgresAuditService()
container.register("audit_logger", lambda c: audit_service_instance)
container.register("audit_query", lambda c: audit_service_instance)
```

---

### `app/__init__.py` (modify - add API blueprint registration)

**Blueprint registration insertion point** (lines 298-320):
```python
from app.blueprints.home import home_bp
from app.blueprints.search import search_bp
from app.blueprints.admin import admin_bp
# ...
app.register_blueprint(admin_bp, url_prefix="/admin")

from app.blueprints.admin.jobs import jobs_api_bp
app.register_blueprint(jobs_api_bp, url_prefix="/api/v2/admin/jobs")
```

**flask-smorest Api initialization must go after config setup (line ~150, after `limiter.init_app(app)`) and before `return app`.**

---

### `app/container.py` (modify - register token service)

**Service registration pattern** (lines 115-194):
```python
def register_services(container: ServiceContainer) -> None:
    # Import services here to avoid circular imports
    from app.services.ldap_service import LDAPService
    # ...

    container.register("ldap_service", lambda c: LDAPService())
    # ...

    logger.info(f"Registered {len(container.list_services())} services")
```

**Insert new registration:**
```python
from app.services.external_api_token_service import ExternalApiTokenService
container.register("external_api_token_service", lambda c: ExternalApiTokenService())
```

---

### `app/templates/admin/_external_api_tokens.html` (component)

**Analog:** `app/templates/admin/_api_tokens.html`

**HTMX card pattern** (lines 1-13):
```html
<div class="bg-white rounded-lg shadow p-4 space-y-4">
    <h3 class="text-base font-medium text-gray-600 mb-4">API Token Management</h3>
    
    <div hx-get="{{ url_for('admin.token_refresh_service_status') }}"
         hx-trigger="load"
         hx-swap="innerHTML">
        <div class="text-center py-2">
            <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-400 mx-auto"></div>
        </div>
    </div>
```

---

## Shared Patterns

### Authentication (Web UI routes)
**Source:** `app/middleware/auth.py` lines 131-179
**Apply to:** `app/blueprints/admin/api_tokens.py` (admin token management routes)
```python
@require_role("admin")
def create_api_token():
    # route logic
```

### Authentication (API routes)
**Source:** New `app/blueprints/api/auth.py` (no existing analog -- bearer token auth is new)
**Apply to:** `app/blueprints/api/search.py`, `app/blueprints/api/users.py`
```python
@require_api_token
def get(self, args):
    # g.api_token is set by decorator
    # g.user is set to f"api:{token.name}"
```

### Audit Logging
**Source:** `app/services/audit_service_postgres.py` lines 71-93
**Apply to:** All admin token CRUD routes, all API search/profile routes
```python
audit_service.log_admin_action(
    user_email=admin_email,
    action="api_token_created",
    target=token_model.name,
    details={"token_id": token_model.id, "token_prefix": token_model.token_prefix}
)
```

### Rate Limiting
**Source:** `app/blueprints/search/__init__.py` lines 35-43 and 1274-1275
**Apply to:** `app/blueprints/api/search.py`, `app/blueprints/api/users.py`
```python
def _search_rate_key() -> str:
    return getattr(g, "user", None) or get_remote_address()

@search_bp.route("/search", methods=["POST"])
@limiter.limit("30/minute", key_func=_search_rate_key)
```
**Adaptation:** Key function returns `f"api_token:{g.api_token.id}"` for per-token buckets.

### Error Handling (JSON responses)
**Source:** `app/utils/error_handler.py` lines 124-132
**Apply to:** All API routes
```python
if json_response:
    return jsonify({
        "error": error_message,
        "error_type": type(e).__name__,
        "error_id": error_id,
        "status": "error",
    }), status_code
```
**Adaptation:** API errors use D-07 format: `{"error": {"code": "...", "message": "...", "details": {...}}}`.

### Container Registration
**Source:** `app/container.py` lines 139-141
**Apply to:** `external_api_token_service`
```python
container.register("external_api_token_service", lambda c: ExternalApiTokenService())
```

### BaseModel + TimestampMixin
**Source:** `app/models/base.py` lines 169-228 (BaseModel) and lines 15-29 (TimestampMixin)
**Apply to:** `app/models/external_api_token.py`
```python
class ExternalApiToken(BaseModel, TimestampMixin):
    __tablename__ = "external_api_tokens"
    # inherits: id, created_at, updated_at, save(), delete(), update(), to_dict()
```

### Test Structure
**Source:** `tests/unit/services/test_audit_service_postgres.py` lines 1-49
**Apply to:** All new test files
```python
import pytest
from app.models.audit import AuditLog
from app.services.audit_service_postgres import PostgresAuditService

pytestmark = pytest.mark.unit

@pytest.fixture
def audit_svc(app, db_session):
    return PostgresAuditService()

def test_log_search_inserts_audit_row(audit_svc, app, db_session):
    audit_svc.log_search(...)
    row = AuditLog.query.filter_by(user_email="user@x.com").first()
    assert row is not None
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/blueprints/api/schemas.py` | utility | transform | No marshmallow schemas exist in codebase. This is the first use of marshmallow. Planner should use RESEARCH.md Pattern 5 (marshmallow envelope schemas) as the reference pattern. |

## Metadata

**Analog search scope:** `app/blueprints/`, `app/models/`, `app/services/`, `app/middleware/`, `app/utils/`, `app/templates/admin/`, `tests/`
**Files scanned:** ~30 files across blueprints, models, services, middleware, and tests
**Pattern extraction date:** 2026-05-17
