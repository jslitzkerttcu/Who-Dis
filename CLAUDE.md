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
python scripts/check_genesys_cache.py       # Test Genesys cache
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

- **Backend**: Flask 3.0.0, SQLAlchemy, PostgreSQL 12+
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
