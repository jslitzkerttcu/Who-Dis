# Architecture

**Analysis Date:** 2026-04-24

## Pattern Overview

**Overall:** Layered architecture with dependency injection container, hybrid server-side + HTMX frontend, and modular blueprint-based request routing.

**Key Characteristics:**
- **Dependency Injection Container**: All services registered centrally in `app/container.py`, resolved at runtime
- **Multi-layer structure**: Models, Services, Blueprints (routes), Middleware (cross-cutting), Interfaces (contracts)
- **HTMX + Jinja2 Frontend**: Server renders HTML fragments for partial page updates; progressive enhancement without large JS bundles
- **Configurable via Database**: Runtime configuration encrypted and stored in PostgreSQL, not hardcoded
- **Concurrent Service Orchestration**: ThreadPoolExecutor-based parallel API calls to LDAP, Genesys, Microsoft Graph
- **Role-based Access Control**: Three-tier role system (viewer, editor, admin) with middleware enforcement

## Layers

**Presentation (Templates & Static):**
- Purpose: Render user-facing HTML and handle client-side interactions
- Location: `app/templates/`, `app/static/`
- Contains: Jinja2 templates organized by feature area, Tailwind CSS, minimal vanilla JS
- Depends on: Flask g context (user, role), blueprint route data
- Used by: Flask routing system via `render_template()`

**Routing & Request Handling (Blueprints):**
- Purpose: Define HTTP endpoints and orchestrate feature-specific request flows
- Location: `app/blueprints/`
- Contains: Five main blueprints - home (auth), search (identity lookup), admin (management), session (lifecycle), utilities (blocked numbers)
- Depends on: Services (via DI container), Models, Middleware
- Used by: Flask app initialization (`create_app()`)

**Middleware (Cross-Cutting Concerns):**
- Purpose: Handle authentication, authorization, session management, audit logging, error handling
- Location: `app/middleware/`
- Contains: `auth.py` (decorator-driven auth flow), `authentication_handler.py` (Azure AD header extraction), `role_resolver.py` (role determination), `session_manager.py` (session lifecycle), `user_provisioner.py` (auto-provision on first login), `csrf.py` (double-submit CSRF), `audit_logger.py` (access attempt logging)
- Depends on: Models (User, UserSession, AccessAttempt), Services (configuration)
- Used by: Route decorators (`@auth_required`, `@require_role("admin")`)

**Business Logic (Services):**
- Purpose: Encapsulate domain logic, API interactions, data transformations, background jobs
- Location: `app/services/`
- Contains: Identity search (LDAP, Genesys, Graph), search coordination (orchestration, result merging, enhancement), configuration management, audit logging, encryption, token refresh, caching
- Depends on: Models, Interfaces, Configuration service, External APIs
- Used by: Blueprints, other services

**Data Access (Models & Repositories):**
- Purpose: Define database schema, provide ORM methods, implement domain object logic
- Location: `app/models/`
- Contains: Base classes (with mixins for timestamps, user tracking, expiration, JSON data), core models (User, Configuration, ApiToken, Session), logging models (AuditLog, AccessAttempt, ErrorLog), cache models (SearchCache, EmployeeProfile, Genesys*), feature models (UserNote, JobCode, SystemRole, JobRoleMapping)
- Depends on: SQLAlchemy, PostgreSQL
- Used by: Services, Blueprints, Middleware

**Dependency Resolution (Container):**
- Purpose: Manage service lifecycle, lazy instantiation, thread-safe singleton pattern
- Location: `app/container.py`
- Contains: ServiceContainer class (register, get, get_all_by_interface), factory functions registered for each service
- Depends on: All service implementations
- Used by: `create_app()` during initialization, services accessing other services via `current_app.container.get("service_name")`

**Interfaces (Contracts):**
- Purpose: Define service interfaces for loose coupling and testability
- Location: `app/interfaces/`
- Contains: Contracts for search services, audit services, cache repositories, configuration, external services, token services
- Depends on: Nothing (pure abstraction)
- Used by: Service implementations, container type checking

## Data Flow

**Search Flow (Most Common):**

1. User enters search term in search page (routed to `search_bp` in `app/blueprints/search/__init__.py`)
2. Route handler validates input and calls `SearchOrchestrator.execute_concurrent_search()`
3. Orchestrator spawns three threads in ThreadPoolExecutor:
   - LDAP search (via `LDAPService.search_user()`)
   - Genesys search (via `GenesysCloudService.search_user()`)
   - Microsoft Graph search (via `GraphService.search_user()`)
4. Each service:
   - Retrieves encrypted API credentials from Configuration service
   - Makes authenticated HTTP request with timeout handling
   - Parses response, handles errors, returns structured result
5. Orchestrator collects results, calls `ResultMerger.merge_results()` to deduplicate/combine data
6. Calls `SearchEnhancer` to add enriched data (employee profiles, photos, job codes)
7. Cache decorator stores result in `SearchCache` table with TTL
8. Route renders template with merged results, uses `_get_photo_element()` to fetch inline base64-encoded photos from `EmployeeProfiles` table
9. Response sent to client; HTMX fragments update page without reload

**Authentication & Session Flow:**

1. Unauthenticated request arrives → `before_request()` sets `g.user = None`, `g.role = None`
2. Route decorated with `@auth_required` calls `authenticate()` middleware:
   - `AuthenticationHandler.authenticate_user()` extracts user email from Azure AD header `X-MS-CLIENT-PRINCIPAL-NAME`
   - `RoleResolver.get_user_role()` looks up role in database; if not found, denies access
   - `auth_required` decorator returns login page with denial reason
3. On login page submit:
   - `authenticate()` runs again, succeeds, proceeds to:
   - `UserProvisioner.get_or_create_user()` inserts or updates User record
   - `SessionManager.get_or_create_session()` creates UserSession with timeout
   - `AuditLogger.log_authentication_success()` logs successful auth event
4. For protected routes:
   - `@require_role("admin")` further restricts to specific role(s)
   - Access denied raises 403 with snarky humor message
5. Session timeout managed by client-side JavaScript polling `/api/session/check` every 30 seconds:
   - Server checks expiration, extends on activity, returns warning if near expiration
   - Client shows modal if warning received; user can extend or logout
   - Session stored in Flask session as `session_id`, linked to database record

**Configuration Flow:**

1. Application bootstrap calls `config_get()` from `ConfigurationService`
2. Service checks cache; if miss, queries `Configuration` table by category.key
3. If encrypted, uses `EncryptionService.decrypt()` with `WHODIS_ENCRYPTION_KEY` env var
4. Caches result in memory for performance
5. Services use `_get_config()` helper to retrieve values with prefix (e.g., "genesys.api_timeout")

**State Management:**

- **Request-level**: Flask `g` object holds current user email and role
- **Session-level**: `UserSession` database records track active sessions with timeout/expiration
- **Application-level**: DI container singleton instances (one per app)
- **Configuration-level**: Encrypted PostgreSQL `Configuration` table with in-memory cache
- **Cache-level**: Specialized models for expensive computations:
  - `SearchCache`: User search results (30-min TTL)
  - `EmployeeProfiles`: Profile photos and metadata (24-hour refresh via background job)
  - `Genesys*`: Genesys organizational hierarchy and contact info (background refresh)

## Key Abstractions

**ServiceContainer (Dependency Injection):**
- Purpose: Provides loose coupling between layers; enables testing via mocks
- Examples: `app/container.py` (registry), services access via `current_app.container.get("service_name")`
- Pattern: Factory functions register lazy-instantiated singletons; `get()` returns cached instance

**BaseConfigurableService:**
- Purpose: Common pattern for services that read encrypted configuration
- Examples: `app/services/base.py` (base class), inherited by `LDAPService`, `GenesysCloudService`, `GraphService`
- Pattern: Services call `self._get_config("key", default)` which prefixes with service name and handles caching

**BaseAPIService:**
- Purpose: Encapsulate HTTP client logic, timeouts, headers, error handling
- Examples: `app/services/base.py`, inherited by `GenesysCloudService`, `GraphService`
- Pattern: `_make_request()` method with `@handle_service_errors` decorator for automatic logging/audit

**ISearchService Interface:**
- Purpose: Contract for services that perform user searches
- Examples: Implemented by `LDAPService`, `GenesysCloudService`, `GraphService`, `SearchOrchestrator`
- Pattern: `search_user(term: str) -> Optional[Dict[str, Any]]` method; enables type checking and container filtering

**ITokenService Interface:**
- Purpose: Contract for services that maintain OAuth tokens
- Examples: Implemented by `GenesysCloudService`, `GraphService`
- Pattern: `refresh_token_if_needed() -> bool` method; container discovers all implementations at startup via `get_all_by_interface()`

**Model Mixins:**
- Purpose: DRY principle for common fields and methods
- Examples: `TimestampMixin` (created_at, updated_at), `UserTrackingMixin` (user_email, ip_address, session_id), `ExpirableMixin` (expires_at, is_expired, cleanup_expired), `JSONDataMixin` (additional_data JSONB field)
- Pattern: Composed into model classes; inherit methods like `save()`, `delete()`, `update()` from `BaseModel`

**Decorator Patterns:**
- Purpose: Aspect-oriented programming for cross-cutting concerns
- Examples: `@auth_required` (enforcement), `@require_role("admin")` (authorization), `@handle_errors` (error handling), `@handle_service_errors` (service-level error logging), `@ensure_csrf_cookie` (CSRF token injection)

## Entry Points

**Application Startup:**
- Location: `run.py`
- Triggers: `python run.py` command
- Responsibilities: Load environment variables, create Flask app via `create_app()`, run on configured host/port

**Flask Application Factory:**
- Location: `app/__init__.py` (`create_app()` function)
- Triggers: Imported by `run.py` and test/deployment contexts
- Responsibilities:
  - Initialize database connection pool
  - Inject dependency container and register services
  - Load configuration from database
  - Initialize CSRF protection, audit service, token refresh background job
  - Register all blueprints
  - Set up global error handlers
  - Clean up expired sessions/tokens on startup

**Authentication Decorator:**
- Location: `app/middleware/auth.py` (`@auth_required`)
- Triggers: Applied to routes requiring login
- Responsibilities: Call `authenticate()` orchestrator, redirect to login if fails, proceed to next handler if passes

**Search Route:**
- Location: `app/blueprints/search/__init__.py` (`/search` and `/api/search`)
- Triggers: User submits search form or API call
- Responsibilities: Validate input, call `SearchOrchestrator`, merge results, serve cached results, render template or JSON

**Admin Routes:**
- Location: `app/blueprints/admin/__init__.py` (multiple subroutes)
- Triggers: User navigates to `/admin/`
- Responsibilities: Manage users, view audit logs, configure system, manage caches, monitor database health

**Session Check (Client-Server Polling):**
- Location: `app/blueprints/session/__init__.py` (`/api/session/check`)
- Triggers: Client JavaScript polls every 30 seconds
- Responsibilities: Check session expiration, extend on activity, signal warning if near expiration, auto-logout if expired

## Error Handling

**Strategy:** Multi-layered approach combining exception catching, logging, auditing, and user-friendly responses.

**Patterns:**

**Route Level** (`@handle_errors` decorator in `app/utils/error_handler.py`):
- Catches all exceptions in route handlers
- Logs to application logger with full stack trace
- Inserts `ErrorLog` record in database for admin visibility
- Creates `AuditLog` entry if user email available
- Returns JSON (for API) or HTML template (for web) with error ID
- Maps exception type to HTTP status code (ValueError → 400, PermissionError → 403, etc.)

**Service Level** (`@handle_service_errors` decorator in `app/utils/error_handler.py`):
- Catches exceptions in service methods
- Logs and optionally audits based on `raise_errors` flag
- Handles `TimeoutError`, `ConnectionError`, `HTTPError` from API calls
- Returns None or raises; caller decides behavior

**Database Query Level** (try/except in models):
- Catches `SQLAlchemyError` when querying or committing
- Logs with context
- Rolls back transaction

**Background Job Level** (token refresh, cache refresh):
- Services handle errors gracefully, continue execution for other services
- Log failures but don't crash app
- Client polling detects failures and shows status warnings

**Middleware Level** (auth, CSRF, session):
- `auth_required` catches auth failures, redirects with denial reason
- CSRF validation fails request silently (403 Forbidden)
- Session manager detects expired sessions, triggers client-side redirect

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module with JSON-compatible format
- Patterns:
  - Application level: `logger.info()`, `logger.error()` to console/file
  - Database level: `ErrorLog.log_error()` stores stack traces for admin visibility
  - Audit level: `AuditLog.log_access()` tracks user actions for compliance

**Validation:**
- Input validation in blueprints (string length, enum values)
- SQLAlchemy model constraints (unique, nullable)
- Email normalization (lowercased, stripped)
- Configuration validation on load (type casting, defaults)

**Authentication:**
- Single provider: Azure AD via header `X-MS-CLIENT-PRINCIPAL-NAME`
- No fallback to basic auth (disabled for security)
- Provisioning: New users auto-created on first login with "viewer" role
- Can be manually promoted to "editor" or "admin" via admin UI

**Authorization:**
- Role-based access control (RBAC) via `@require_role("admin")` decorator
- Roles stored in database, loaded in `RoleResolver`
- Hierarchy enforced in CLAUDE.md (Admin > Editor > Viewer)
- All role lists in database, migrated from environment variables

**CSRF Protection:**
- Double-submit pattern: token in cookie, token in form/header
- Implementation in `app/middleware/csrf.py`
- Token injected via `@ensure_csrf_cookie` decorator before rendering forms
- Client must include token in POST/PUT/DELETE requests

**Security Headers:**
- CSP (Content Security Policy): Restrict script sources
- X-Frame-Options: deny (prevent clickjacking)
- X-Content-Type-Options: nosniff (prevent MIME sniffing)
- Implemented in `app/middleware/security_headers.py`

**Session Management:**
- Timeout: Configurable minutes (default 15)
- Warning: Shows modal N minutes before expiration (default 2)
- Extends: Automatically on user activity or manual request
- Cleanup: Expired sessions removed on startup and via scheduled background task
- Tracking: IP address, user agent, session ID recorded for audit

**Encryption:**
- Framework: `cryptography` library (Fernet symmetric encryption)
- Keys: `WHODIS_ENCRYPTION_KEY` from environment, unique salt per installation in `.whodis_salt`
- Use case: Configuration service encrypts sensitive values (API keys, passwords)
- Pattern: `EncryptionService.encrypt()` / `decrypt()` called on read/write

**Concurrency:**
- Background services: Token refresh, cache refresh run in background threads
- Request threads: Search orchestrator uses `ThreadPoolExecutor` for parallel API calls
- Thread safety: Container uses locks, session-scoped database connections, `copy_current_request_context()` for Flask context in threads
- Timeouts: Each concurrent search has individual timeout; overall timeout prevents hanging

**Observability:**
- Health checks: Database connectivity, API token validity, cache freshness
- Status endpoints: `/admin/api/database/health`, `/admin/api/cache/status`, `/admin/api/tokens/status`
- Monitoring: Admin can view error logs, audit logs, session activity
- Metrics: Table row counts, query performance (PostgreSQL ANALYZE)
