# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
# Set up virtual environment (if not already created)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL database
psql -U whodis_user -d whodis_db -h localhost -f database/create_tables.sql

# Analyze tables for proper statistics (prevents -1 row counts)
psql -U postgres -d whodis_db -h localhost -f database/analyze_tables.sql

# Verify encrypted configuration (for new installs)
python scripts/verify_encrypted_config.py

# Run the application
python run.py
```

The application runs on http://localhost:5000 with debug mode configurable in database.

### Code Quality
```bash
# Linting with ruff
ruff check --fix

# Type checking with mypy
mypy app/ scripts/

# Code formatting (if needed)
black .
```

### Testing
No test framework is currently configured. When implementing tests, add pytest to requirements.txt.

### Key Database Management Scripts
```bash
# Configuration management
python scripts/check_config_status.py       # Check status
python scripts/verify_encrypted_config.py   # Verify encryption
python scripts/diagnose_config.py           # Diagnose problems

# Data synchronization
python scripts/refresh_employee_profiles.py refresh  # Sync employee data

# Cache management
python scripts/debug/check_genesys_cache.py  # Test Genesys cache
```

See [Database Documentation](docs/database.md) for complete database setup and troubleshooting.

## Architecture Overview

WhoDis is a Flask-based identity lookup service with PostgreSQL backend and integrated search across multiple identity providers using a modern hybrid server-side + HTMX architecture.

### Application Structure

**Core Components:**
- **`app/__init__.py`**: Application factory with Flask initialization
- **`app/container.py`**: Dependency injection container for service management
- **`app/database.py`**: Database configuration and connection pooling
- **`run.py`**: Application entry point

**Blueprints** (`app/blueprints/`):
- `home`: Landing page and login
- `search`: Identity search interface (requires 'viewer' role)
- `admin`: User management, config editor, audit logs, job role compliance (requires 'admin')
- `session`: Session timeout management
- `utilities`: Blocked numbers management (role-based)

**Middleware** (`app/middleware/`):
- `authentication_handler.py`: Azure AD header processing
- `role_resolver.py`: Role determination from database/config
- `user_provisioner.py`: Auto-provision users on first login
- `session_manager.py`: Session lifecycle and timeout tracking
- `auth.py`: Authentication orchestration with `@auth_required` decorator
- `csrf.py`, `security_headers.py`, `errors.py`, `audit_logger.py`

**Models** (`app/models/`):
- Base classes with mixins for common patterns (timestamps, user tracking, expiration)
- Core: User, Configuration, ApiToken, Session
- Logging: AuditLog, AccessAttempt, ErrorLog
- Cache: SearchCache, EmployeeProfile, Genesys* models
- Features: UserNote, JobCode, SystemRole, JobRoleMapping

**Services** (`app/services/`):
- Identity providers: LDAPService, GenesysCloudService, GraphService
- Search coordination: SearchOrchestrator, ResultMerger, SearchEnhancer
- Infrastructure: ConfigurationService, EncryptionService, AuditServicePostgres
- Job role compliance: JobRoleMappingService, JobRoleWarehouseService, ComplianceCheckingService

**Detailed architecture documentation:** See [docs/architecture.md](docs/architecture.md)

### Frontend Architecture

**Hybrid server-side + HTMX approach:**
- Jinja2 templates for initial page structure and SEO-friendly content
- HTMX for dynamic content updates without page refreshes
- Tailwind CSS for responsive, mobile-first styling
- Minimal vanilla JavaScript for enhanced functionality

**Benefits:**
- Progressive enhancement (works without JavaScript)
- Fast initial loads with no large JS bundles
- Server returns HTML fragments, not JSON APIs
- Simple debugging

### Key Technologies

- **Backend**: Flask 3.1, SQLAlchemy, PostgreSQL 12+
- **Auth**: Azure AD SSO (X-MS-CLIENT-PRINCIPAL-NAME header)
- **APIs**: ldap3, MSAL (Graph), requests (Genesys)
- **Frontend**: Jinja2, HTMX, Tailwind CSS, FontAwesome
- **Encryption**: cryptography (Fernet)
- **Background**: Threading for token refresh and cache updates

For complete tech stack details, see [README.md](README.md#-tech-stack).

## Critical Implementation Patterns

### Dependency Injection

**Retrieve services from container, never use global imports:**
```python
# Correct
ldap_service = current_app.container.get("ldap_service")

# Also correct (in services)
@property
def ldap_service(self):
    if self._ldap_service is None:
        self._ldap_service = current_app.container.get("ldap_service")
    return self._ldap_service
```

See [docs/architecture.md#dependency-injection-container](docs/architecture.md#dependency-injection-container) for details.

### Authentication & Authorization

**Always use decorators on routes:**
```python
@blueprint.route("/my-route")
@auth_required
@require_role("editor")  # or "viewer", "admin"
def my_route():
    user_email = g.user  # Current user email
    ip_address = format_ip_info()  # IP from headers
    # Route logic
```

**Role hierarchy:** Admin > Editor > Viewer

### Model Patterns

**Extend appropriate base classes:**
```python
from app.models.base import BaseModel, TimestampMixin

class MyModel(BaseModel, TimestampMixin):
    __tablename__ = "my_table"

    # Fields
    name = db.Column(db.String(255), nullable=False)

    # Use inherited methods
    def custom_logic(self):
        self.update(name="new name")  # From BaseModel
```

**Available mixins:**
- `TimestampMixin`: `created_at`, `updated_at`
- `UserTrackingMixin`: `user_email`, `ip_address`, `user_agent`, `session_id`
- `ExpirableMixin`: `expires_at`, `is_expired` property
- `JSONDataMixin`: `data` JSONB field with helpers

### Service Patterns

**Implement appropriate interfaces and extend base classes:**
```python
from app.interfaces.search_service import ISearchService
from app.services.base import BaseSearchService

class MySearchService(BaseSearchService, ISearchService):
    def __init__(self):
        super().__init__("my_service")  # Config category

    def search_user(self, term: str) -> Optional[Dict[str, Any]]:
        # Implementation with timeout handling
        pass
```

**Register in container** (`app/container.py`):
```python
container.register("my_service", lambda c: MySearchService())
```

### Error Handling

**Use decorator for service methods:**
```python
from app.utils.error_handler import handle_service_errors

@handle_service_errors(raise_errors=False)
def my_service_method(self):
    # Service logic
    # Errors automatically logged and handled
```

**Log and audit errors:**
```python
try:
    # Operation
except Exception as e:
    logger.error(f"Operation failed: {str(e)}", exc_info=True)
    audit_service.log_error(
        error_type="operation_error",
        message=str(e),
        user_email=g.user
    )
```

### Concurrent Operations

**Use SearchOrchestrator pattern for parallel API calls:**
```python
from concurrent.futures import ThreadPoolExecutor
from flask import copy_current_request_context

with ThreadPoolExecutor(max_workers=3) as executor:
    future1 = executor.submit(
        copy_current_request_context(service1.method),
        arg
    )
    future2 = executor.submit(
        copy_current_request_context(service2.method),
        arg
    )

    result1 = future1.result(timeout=3)
    result2 = future2.result(timeout=5)
```

## Common Development Tasks

### Adding a New Service

1. Create service class implementing appropriate interface
2. Extend base service class for common functionality
3. Register factory in `app/container.py`'s `register_services()` function
4. Access via `current_app.container.get("service_name")`

### Adding a New Model

1. Create model class extending appropriate base/mixins
2. Define relationships using SQLAlchemy conventions
3. Add migration SQL to `database/create_tables.sql`
4. Run `ANALYZE table_name` after first data insertion for proper statistics

### Adding a New Blueprint Route

1. Create route in appropriate blueprint
2. Apply auth decorators: `@auth_required` and `@require_role("role_name")`
3. Use `g.user` for current user email, `format_ip_info()` for IP address
4. Log actions with `audit_service.log_search()` or `audit_service.log_admin_action()`
5. Return HTMX fragments for partial updates, full templates for initial loads

### Adding a New Configuration Value

1. Add to encrypted configuration via admin UI or script
2. Access with `config_get("category", "key", "default")`
3. Never hardcode sensitive values

## Performance Guidelines

### Database Optimization

1. **Avoid N+1 Queries**: Use `joinedload()` or bulk queries
   ```python
   # Bad
   for job_code in job_codes:
       count = job_code.mappings.count()  # N+1 query

   # Good
   mapping_counts = db.session.query(
       JobRoleMapping.job_code_id,
       func.count(JobRoleMapping.id)
   ).group_by(JobRoleMapping.job_code_id).all()
   ```

2. **Client-Side Filtering**: For datasets < 1000 rows, filter in JavaScript to reduce server load

3. **Progressive Loading**: Use pagination or "Load More" patterns for tables with 100+ rows

4. **Lazy Loading**: Default to lazy loading for expensive operations (photos, large text fields)

5. **Index Strategically**: Add indexes on foreign keys and frequently filtered columns

6. **Cache Aggressively**: Use PostgreSQL cache with appropriate TTLs
   - Search results: 30 minutes
   - API tokens: Auto-managed by expiration
   - Employee profiles: 24 hours

### Frontend Performance

1. **HTMX Fragments**: Return minimal HTML, not full pages
2. **Lazy Images**: Use lazy loading for profile photos
3. **Client-Side State**: Use JavaScript for UI state, HTMX for data
4. **Debounce Input**: Debounce search inputs to reduce server requests

## Important Database Notes

### Environment Variables Bootstrap Problem

- PostgreSQL credentials MUST remain in `.env` file (chicken-and-egg problem)
- Use `os.getenv()` for database connection, NOT `config_get()`
- Configuration service requires database connection to function

### Encryption Key Management

- `WHODIS_ENCRYPTION_KEY` encrypts all configuration values
- Changing this key makes all encrypted data unreadable
- Always export config before key changes: `python scripts/export_config.py`

### Memory Objects

- PostgreSQL BYTEA columns return memoryview/buffer objects
- Always handle with: `bytes(memoryview_object)` before encryption/decryption

### Table Statistics

- Run `ANALYZE table_name` after creating and populating new tables
- Prevents -1 row counts in admin UI
- PostgreSQL needs statistics for query planning

## Security Considerations

### What's Protected

- All API credentials encrypted at rest using Fernet
- `SECRET_KEY` stored encrypted in database
- Unique salt per installation (.whodis_salt file)
- All authentication events logged
- CSRF protection on state-changing operations
- Security headers (CSP, X-Frame-Options, etc.)
- Session hijacking prevention with timeout tracking

### What to Avoid

- Never commit `.env` file (contains POSTGRES_PASSWORD and WHODIS_ENCRYPTION_KEY)
- Never commit `.whodis_salt` file in production
- Never log sensitive data in plaintext
- Never use basic auth (Azure AD SSO only)
- Never skip authentication decorators on routes
- Never trust user input (use escapeHtml() in templates)

For complete security details, see [README.md#-security-best-practices](README.md#-security-best-practices).

## Key Features Documentation

- **Search Architecture**: See [docs/architecture.md#search-architecture](docs/architecture.md#search-architecture)
- **Job Role Compliance**: See [docs/job-role-compliance.md](docs/job-role-compliance.md)
- **Database Management**: See [docs/database.md](docs/database.md)
- **API Integrations**: See [README.md#-api-integrations](README.md#-api-integrations)
- **Configuration Management**: See [README.md#-configuration-management](README.md#-configuration-management)

## Troubleshooting Quick Reference

### Configuration Issues
```bash
python scripts/check_config_status.py        # Check configuration
python scripts/verify_encrypted_config.py    # Verify encryption
python scripts/diagnose_config.py            # Diagnose problems
```

### Common Problems

**"Error decrypting configuration"**
- Check `WHODIS_ENCRYPTION_KEY` in `.env`
- Run `python scripts/verify_encrypted_config.py`

**"Database connection failed"**
- Verify PostgreSQL is running
- Check credentials in `.env`
- Ensure database exists

**"No search results"**
- Check service credentials in configuration
- Review audit logs: `SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10`

For detailed troubleshooting, see [docs/database.md#troubleshooting](docs/database.md#troubleshooting).

## Additional Resources

- **README.md**: User-facing documentation, installation, features
- **docs/architecture.md**: Detailed architecture and design patterns
- **docs/database.md**: Database setup, configuration, maintenance
- **docs/job-role-compliance.md**: Job role compliance matrix documentation
- **docs/PLANNING.md**: Project roadmap and strategic planning
- **CHANGELOG.md**: Version history and release notes

<!-- GSD:project-start source:PROJECT.md -->
## Project

**WhoDis v3.0 — IT Operations Platform**

WhoDis is an enterprise identity lookup and IT operations platform for a small IT service desk team (~4-5 users). It provides unified search across Active Directory, Microsoft Graph, and Genesys Cloud with role-based access, encrypted configuration, comprehensive audit logging, and a modern HTMX+Tailwind UI. This milestone evolves WhoDis from a lookup tool into a production-grade IT operations platform with reporting, write operations, and API access.

**Core Value:** IT staff can find everything they need to know about any employee — and act on it — from a single interface, without switching between AD, Azure portal, Genesys admin, or M365 admin center.

### Constraints

- **Tech stack:** Flask/PostgreSQL/HTMX — extend existing patterns, don't introduce new frameworks
- **Auth:** Azure AD SSO only — all new endpoints must use existing auth decorators
- **Security:** All write operations require audit trail, confirmation workflows, and appropriate role checks
- **API permissions:** Graph API features may require additional Azure AD app permissions (document requirements per feature)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.8+ - Backend application, services, and scripts
- Jinja2 - Server-side templating for HTML
- HTML5 - Frontend markup with HTMX enhancement
- CSS3 - Styling via Tailwind CSS utility classes
- JavaScript - Minimal client-side interactivity and HTMX integration
## Runtime
- Python 3.8+ (interpreter and standard library)
- pip with venv (standard Python virtual environments)
- Lockfile: None (uses requirements.txt pinned versions)
## Frameworks
- Flask 3.1.3 - Web framework with blueprint-based architecture
- Flask-SQLAlchemy 3.1.1 - ORM integration for database models
- Flask-WTF 1.2.2 - CSRF protection via double-submit cookie pattern
- SQLAlchemy 2.0.45 - Object-relational mapping and query builder
- cryptography 46.0.7 - Fernet encryption for configuration values
- msal 1.34.0 - Microsoft Authentication Library for Graph API
- ldap3 2.9.1 - LDAP/Active Directory client
- requests 2.33.0 - HTTP client for REST APIs
- httpx 0.28.1 - Alternative async HTTP client (included but requests primary)
- psycopg2-binary 2.9.11 - PostgreSQL adapter for Python
- python-dotenv 1.2.2 - Environment variable loading from .env
- psutil - System utilities and resource monitoring
- pyodbc 5.3.0 - ODBC database driver (legacy support)
- pytz 2025.2 - Timezone handling and conversions
- tabulate 0.9.0 - Formatted table output for CLI tools
- ruff - Fast Python linter and code formatter
- mypy - Static type checking for Python
- types-* packages - Type stubs for dependencies (tabulate, flask, requests, psycopg2, pytz, cryptography)
- Tailwind CSS - Utility-first CSS framework (referenced in templates)
- FontAwesome - Icon library (referenced in templates)
- HTMX - Client-side HTML interactivity (referenced in templates)
## Key Dependencies
- Flask 3.1.3 - Web framework, routing, request handling
- SQLAlchemy 2.0.45 - Data persistence abstraction layer
- psycopg2-binary 2.9.11 - PostgreSQL connectivity (required for production)
- ldap3 2.9.1 - Active Directory/LDAP integration for employee search
- msal 1.34.0 - OAuth2 token acquisition for Microsoft Graph API
- requests 2.33.0 - HTTP client for Genesys Cloud and Graph APIs
- cryptography 46.0.7 - Fernet encryption for stored configuration
- ruff - Code linting and style enforcement
- mypy - Type checking (enables `--strict` mode per CLAUDE.md)
## Configuration
- .env file (required, not committed) with:
- Database-stored encrypted configuration via Configuration model (`app/models/configuration.py`)
- Configuration accessed via `config_get()` functions (automatic decryption)
- No build step required (pure Python Flask application)
- Dependency installation: `pip install -r requirements.txt`
- Database initialization: SQL files in `database/` directory
- Virtual environment: Standard Python venv
## Platform Requirements
- Python 3.8+
- PostgreSQL 12+ (required, SQLite fallback available but not recommended)
- Virtual environment (venv)
- Python 3.8+ runtime
- PostgreSQL 12+ database
- Web server: Gunicorn, uWSGI, or Azure App Service
- Reverse proxy: Nginx or Azure App Service (SSL/TLS termination)
## Port Configuration
- Flask development: 5000 (configurable via database configuration)
- PostgreSQL: 5432 (default)
## Encryption
- Algorithm: Fernet (symmetric encryption via `cryptography` library)
- Key: WHODIS_ENCRYPTION_KEY (base64-encoded 32-byte key)
- Per-installation salt: `.whodis_salt` file
- Sensitive values encrypted at rest in PostgreSQL configuration table
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Modules use `snake_case`: `authentication_handler.py`, `search_orchestrator.py`, `user_provisioner.py`
- Blueprints in subdirectories: `app/blueprints/{feature}/__init__.py` contains blueprint routes
- Services in dedicated files: `app/services/{service_name}.py`
- Models in dedicated files: `app/models/{model_name}.py`
- Interfaces in `app/interfaces/`: `{service_type}.py` (e.g., `search_service.py`, `cache_repository.py`)
- Public methods use `snake_case`: `search_user()`, `get_or_create()`, `update_last_login()`
- Private methods prefixed with `_`: `_get_config()`, `_normalize_search_term()`, `_make_request()`
- Decorators prefixed with `@`: `@auth_required`, `@require_role()`, `@handle_errors`, `@abstractmethod`
- Helper/utility functions in separate modules: `app/utils/error_handler.py`, `app/utils/ip_utils.py`
- Use `snake_case` for all variables: `user_email`, `cache_key`, `search_term`, `service_name`
- Private instance variables prefixed with `_`: `self._config_cache`, `self._base_url`, `self._token_service_name`
- Constants in `UPPER_CASE`: `ROLE_VIEWER = "viewer"`, `ROLE_ADMIN = "admin"`
- Class constants for enums: `User.ROLE_VIEWER`, `User.ROLE_EDITOR`
- Class names use `PascalCase`: `BaseModel`, `SearchOrchestrator`, `AuthenticationHandler`
- Interface/Abstract classes prefixed with `I`: `ISearchService`, `ICacheRepository`, `IConfigurationService`
- Model classes named singularly: `User`, `UserNote`, `ApiToken`, `ErrorLog`
- Mixin classes suffixed with `Mixin`: `TimestampMixin`, `UserTrackingMixin`, `ExpirableMixin`, `JSONDataMixin`
## Code Style
- Black-compatible formatting (no explicit config, but follows Python standard)
- 4-space indentation throughout
- Line length is not strictly enforced but kept reasonable (80-120 chars typical)
- Double quotes for strings: `"string"` preferred over `'string'`
- Tool: `ruff` (in requirements.txt, no config file)
- Run: `ruff check --fix`
- Type checking: `mypy` with config at `mypy.ini`
- Run: `mypy app/ scripts/`
- Located at: `mypy.ini`
- Settings: `python_version = 3.8`, `warn_return_any = True`
- Ignores third-party library stubs: `ldap3`, `msal`, `flask_sqlalchemy`, `sqlalchemy`, `dotenv`, `httpx`
- Special handling for `app.models` and `app.database` (allows implicit optionals for SQLAlchemy)
## Import Organization
- No path aliases configured; use absolute imports from `app/` root
- Example: `from app.models.user import User` (not relative imports)
- Blueprint __init__.py files contain routes: `app/blueprints/admin/__init__.py`
- Model imports in selective __init__.py files: `from app.models import ErrorLog` works via explicit imports
## Error Handling
- Decorator-based: `@handle_errors` for routes, `@handle_service_errors` for services
- Located in: `app/utils/error_handler.py`
- Route handler signature:
- Service method signature:
- `ValueError` → HTTP 400
- `PermissionError` → HTTP 403
- `FileNotFoundError` → HTTP 404
- `SQLAlchemyError` → HTTP 500 with generic "Database error occurred"
- All others → HTTP 500
- Use module-level logger: `logger = logging.getLogger(__name__)`
- Log levels:
- Example: `logger.error(f"Error in {service}.{method}: {str(e)}", exc_info=True)`
## Logging
- Module logger initialization: `logger = logging.getLogger(__name__)` at module top
- Service loggers: Include service name in log messages for traceability
- Audit logging: Use `audit_service.log_error()` for error tracking with user context
- Sensitive data redaction: Request data sanitized before logging (passwords, tokens)
- Request entry points: Log HTTP method, URL, user
- API calls: Log `logger.debug()` for request, `logger.debug()` for response status
- Errors: Always use `logger.error(..., exc_info=True)` with full traceback
- Timing: Log start/completion for long operations (cache refresh, bulk operations)
- Configuration: Log config load success/failure at startup
## Comments
- Complex business logic: Document the "why", not the "what"
- Non-obvious algorithmic choices: Explain rationale
- Workarounds: Mark with `# NOTE:` or `# HACK:` when working around known issues
- Integration points: Comment when interfacing with external APIs
- Not used (Python codebase)
- Docstrings used instead: Follow Google/NumPy style
- Module docstrings: First line is brief description
- Function docstrings: Brief summary, Args, Returns, optional Raises
- Example from `app/models/base.py`:
- Mandatory for: Public APIs, service methods, interfaces, decorators
- Optional for: Internal helper functions, simple getters
- Location: Immediately after function/class definition
## Function Design
- Typical service methods: 20-40 lines
- Longer methods: 50-100 lines acceptable for complex orchestration
- Guideline: If exceeds 100 lines, consider extracting helper methods
- Example: `search_orchestrator.search()` = 80 lines combining multiple steps
- Explicit parameters over kwargs: `def search_user(self, search_term: str)`
- Type hints for all public methods: `search_term: str`, `commit: bool = True`
- Optional params with defaults: `cache_repository: Optional[ICacheRepository] = None`
- Maximum reasonable params: 4-5; use objects for more complex signatures
- Explicit type hints: `-> Optional[Dict[str, Any]]`, `-> bool`, `-> List[User]`
- Consistent return types: Don't return either list or single object; use multiple_results wrapper
- Single responsibility: Return one logical result, not multiple unrelated values
- Pattern from `BaseSearchService`: Return `Optional[Dict]` with possible `multiple_results` flag
## Module Design
- Explicit imports in blueprints: `from app.models import User` works if models/__init__.py exports
- Service classes exported as singletons or via container: `from app.services.genesys_service import genesys_service`
- Interfaces imported directly: `from app.interfaces.search_service import ISearchService`
- Used selectively in `app/blueprints/{name}/__init__.py` (contains blueprint + routes)
- Not used for services or models (import directly)
- Example: `app/models/__init__.py` may not exist; import `from app.models.user import User` directly
- Local imports inside functions when needed: `from app.models.session import UserSession`
- Service container accessed via `current_app.container.get()` to avoid circular deps
- Interfaces used as type hints to decouple dependencies
- Mixins for code reuse: `class User(BaseModel, TimestampMixin)` combines behaviors
- Base classes for common patterns: `BaseAPIService`, `BaseTokenService`, `BaseSearchService`
- Multiple inheritance pattern: `BaseAPITokenService(BaseTokenService, BaseSearchService)` for combined functionality
## Configuration Access
- Import function: `from app.services.configuration_service import config_get`
- Usage: `config_get("category.key", "default_value")`
- Never hardcode secrets; always use config_get
- Example: `ldap_server = config_get("ldap.server", "localhost")`
- Override in __init__: `self._config_prefix = "service_name"`
- Retrieve in methods: `self._get_config("key", "default")`
- Caching built-in: `self._config_cache` dict prevents repeated lookups
## Decorator Patterns
- Use `@auth_required` on all protected routes
- Combine with `@require_role("admin")` or `@require_role("viewer")`
- Location: `app/middleware/auth.py`
- Pattern: Always on top of function stack
- `@handle_errors` for routes (returns HTML or JSON)
- `@handle_service_errors` for service methods (logs and re-raises or returns default)
- No explicit decorator; use model save(commit=True/False)
- Batch operations: Set commit=False, then call db.session.commit() once
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- **Dependency Injection Container**: All services registered centrally in `app/container.py`, resolved at runtime
- **Multi-layer structure**: Models, Services, Blueprints (routes), Middleware (cross-cutting), Interfaces (contracts)
- **HTMX + Jinja2 Frontend**: Server renders HTML fragments for partial page updates; progressive enhancement without large JS bundles
- **Configurable via Database**: Runtime configuration encrypted and stored in PostgreSQL, not hardcoded
- **Concurrent Service Orchestration**: ThreadPoolExecutor-based parallel API calls to LDAP, Genesys, Microsoft Graph
- **Role-based Access Control**: Three-tier role system (viewer, editor, admin) with middleware enforcement
## Layers
- Purpose: Render user-facing HTML and handle client-side interactions
- Location: `app/templates/`, `app/static/`
- Contains: Jinja2 templates organized by feature area, Tailwind CSS, minimal vanilla JS
- Depends on: Flask g context (user, role), blueprint route data
- Used by: Flask routing system via `render_template()`
- Purpose: Define HTTP endpoints and orchestrate feature-specific request flows
- Location: `app/blueprints/`
- Contains: Five main blueprints - home (auth), search (identity lookup), admin (management), session (lifecycle), utilities (blocked numbers)
- Depends on: Services (via DI container), Models, Middleware
- Used by: Flask app initialization (`create_app()`)
- Purpose: Handle authentication, authorization, session management, audit logging, error handling
- Location: `app/middleware/`
- Contains: `auth.py` (decorator-driven auth flow), `authentication_handler.py` (Azure AD header extraction), `role_resolver.py` (role determination), `session_manager.py` (session lifecycle), `user_provisioner.py` (auto-provision on first login), `csrf.py` (double-submit CSRF), `audit_logger.py` (access attempt logging)
- Depends on: Models (User, UserSession, AccessAttempt), Services (configuration)
- Used by: Route decorators (`@auth_required`, `@require_role("admin")`)
- Purpose: Encapsulate domain logic, API interactions, data transformations, background jobs
- Location: `app/services/`
- Contains: Identity search (LDAP, Genesys, Graph), search coordination (orchestration, result merging, enhancement), configuration management, audit logging, encryption, token refresh, caching
- Depends on: Models, Interfaces, Configuration service, External APIs
- Used by: Blueprints, other services
- Purpose: Define database schema, provide ORM methods, implement domain object logic
- Location: `app/models/`
- Contains: Base classes (with mixins for timestamps, user tracking, expiration, JSON data), core models (User, Configuration, ApiToken, Session), logging models (AuditLog, AccessAttempt, ErrorLog), cache models (SearchCache, EmployeeProfile, Genesys*), feature models (UserNote, JobCode, SystemRole, JobRoleMapping)
- Depends on: SQLAlchemy, PostgreSQL
- Used by: Services, Blueprints, Middleware
- Purpose: Manage service lifecycle, lazy instantiation, thread-safe singleton pattern
- Location: `app/container.py`
- Contains: ServiceContainer class (register, get, get_all_by_interface), factory functions registered for each service
- Depends on: All service implementations
- Used by: `create_app()` during initialization, services accessing other services via `current_app.container.get("service_name")`
- Purpose: Define service interfaces for loose coupling and testability
- Location: `app/interfaces/`
- Contains: Contracts for search services, audit services, cache repositories, configuration, external services, token services
- Depends on: Nothing (pure abstraction)
- Used by: Service implementations, container type checking
## Data Flow
- **Request-level**: Flask `g` object holds current user email and role
- **Session-level**: `UserSession` database records track active sessions with timeout/expiration
- **Application-level**: DI container singleton instances (one per app)
- **Configuration-level**: Encrypted PostgreSQL `Configuration` table with in-memory cache
- **Cache-level**: Specialized models for expensive computations:
## Key Abstractions
- Purpose: Provides loose coupling between layers; enables testing via mocks
- Examples: `app/container.py` (registry), services access via `current_app.container.get("service_name")`
- Pattern: Factory functions register lazy-instantiated singletons; `get()` returns cached instance
- Purpose: Common pattern for services that read encrypted configuration
- Examples: `app/services/base.py` (base class), inherited by `LDAPService`, `GenesysCloudService`, `GraphService`
- Pattern: Services call `self._get_config("key", default)` which prefixes with service name and handles caching
- Purpose: Encapsulate HTTP client logic, timeouts, headers, error handling
- Examples: `app/services/base.py`, inherited by `GenesysCloudService`, `GraphService`
- Pattern: `_make_request()` method with `@handle_service_errors` decorator for automatic logging/audit
- Purpose: Contract for services that perform user searches
- Examples: Implemented by `LDAPService`, `GenesysCloudService`, `GraphService`, `SearchOrchestrator`
- Pattern: `search_user(term: str) -> Optional[Dict[str, Any]]` method; enables type checking and container filtering
- Purpose: Contract for services that maintain OAuth tokens
- Examples: Implemented by `GenesysCloudService`, `GraphService`
- Pattern: `refresh_token_if_needed() -> bool` method; container discovers all implementations at startup via `get_all_by_interface()`
- Purpose: DRY principle for common fields and methods
- Examples: `TimestampMixin` (created_at, updated_at), `UserTrackingMixin` (user_email, ip_address, session_id), `ExpirableMixin` (expires_at, is_expired, cleanup_expired), `JSONDataMixin` (additional_data JSONB field)
- Pattern: Composed into model classes; inherit methods like `save()`, `delete()`, `update()` from `BaseModel`
- Purpose: Aspect-oriented programming for cross-cutting concerns
- Examples: `@auth_required` (enforcement), `@require_role("admin")` (authorization), `@handle_errors` (error handling), `@handle_service_errors` (service-level error logging), `@ensure_csrf_cookie` (CSRF token injection)
## Entry Points
- Location: `run.py`
- Triggers: `python run.py` command
- Responsibilities: Load environment variables, create Flask app via `create_app()`, run on configured host/port
- Location: `app/__init__.py` (`create_app()` function)
- Triggers: Imported by `run.py` and test/deployment contexts
- Responsibilities:
- Location: `app/middleware/auth.py` (`@auth_required`)
- Triggers: Applied to routes requiring login
- Responsibilities: Call `authenticate()` orchestrator, redirect to login if fails, proceed to next handler if passes
- Location: `app/blueprints/search/__init__.py` (`/search` and `/api/search`)
- Triggers: User submits search form or API call
- Responsibilities: Validate input, call `SearchOrchestrator`, merge results, serve cached results, render template or JSON
- Location: `app/blueprints/admin/__init__.py` (multiple subroutes)
- Triggers: User navigates to `/admin/`
- Responsibilities: Manage users, view audit logs, configure system, manage caches, monitor database health
- Location: `app/blueprints/session/__init__.py` (`/api/session/check`)
- Triggers: Client JavaScript polls every 30 seconds
- Responsibilities: Check session expiration, extend on activity, signal warning if near expiration, auto-logout if expired
## Error Handling
- Catches all exceptions in route handlers
- Logs to application logger with full stack trace
- Inserts `ErrorLog` record in database for admin visibility
- Creates `AuditLog` entry if user email available
- Returns JSON (for API) or HTML template (for web) with error ID
- Maps exception type to HTTP status code (ValueError → 400, PermissionError → 403, etc.)
- Catches exceptions in service methods
- Logs and optionally audits based on `raise_errors` flag
- Handles `TimeoutError`, `ConnectionError`, `HTTPError` from API calls
- Returns None or raises; caller decides behavior
- Catches `SQLAlchemyError` when querying or committing
- Logs with context
- Rolls back transaction
- Services handle errors gracefully, continue execution for other services
- Log failures but don't crash app
- Client polling detects failures and shows status warnings
- `auth_required` catches auth failures, redirects with denial reason
- CSRF validation fails request silently (403 Forbidden)
- Session manager detects expired sessions, triggers client-side redirect
## Cross-Cutting Concerns
- Framework: Python `logging` module with JSON-compatible format
- Patterns:
- Input validation in blueprints (string length, enum values)
- SQLAlchemy model constraints (unique, nullable)
- Email normalization (lowercased, stripped)
- Configuration validation on load (type casting, defaults)
- Single provider: Azure AD via header `X-MS-CLIENT-PRINCIPAL-NAME`
- No fallback to basic auth (disabled for security)
- Provisioning: New users auto-created on first login with "viewer" role
- Can be manually promoted to "editor" or "admin" via admin UI
- Role-based access control (RBAC) via `@require_role("admin")` decorator
- Roles stored in database, loaded in `RoleResolver`
- Hierarchy enforced in CLAUDE.md (Admin > Editor > Viewer)
- All role lists in database, migrated from environment variables
- Double-submit pattern: token in cookie, token in form/header
- Implementation in `app/middleware/csrf.py`
- Token injected via `@ensure_csrf_cookie` decorator before rendering forms
- Client must include token in POST/PUT/DELETE requests
- CSP (Content Security Policy): Restrict script sources
- X-Frame-Options: deny (prevent clickjacking)
- X-Content-Type-Options: nosniff (prevent MIME sniffing)
- Implemented in `app/middleware/security_headers.py`
- Timeout: Configurable minutes (default 15)
- Warning: Shows modal N minutes before expiration (default 2)
- Extends: Automatically on user activity or manual request
- Cleanup: Expired sessions removed on startup and via scheduled background task
- Tracking: IP address, user agent, session ID recorded for audit
- Framework: `cryptography` library (Fernet symmetric encryption)
- Keys: `WHODIS_ENCRYPTION_KEY` from environment, unique salt per installation in `.whodis_salt`
- Use case: Configuration service encrypts sensitive values (API keys, passwords)
- Pattern: `EncryptionService.encrypt()` / `decrypt()` called on read/write
- Background services: Token refresh, cache refresh run in background threads
- Request threads: Search orchestrator uses `ThreadPoolExecutor` for parallel API calls
- Thread safety: Container uses locks, session-scoped database connections, `copy_current_request_context()` for Flask context in threads
- Timeouts: Each concurrent search has individual timeout; overall timeout prevents hanging
- Health checks: Database connectivity, API token validity, cache freshness
- Status endpoints: `/admin/api/database/health`, `/admin/api/cache/status`, `/admin/api/tokens/status`
- Monitoring: Admin can view error logs, audit logs, session activity
- Metrics: Table row counts, query performance (PostgreSQL ANALYZE)
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
