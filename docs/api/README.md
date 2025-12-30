# WhoDis API Documentation

This directory contains technical API documentation for WhoDis services and models.

## Documentation Contents

- **[Services API](services.md)** - Service layer interfaces and implementations
- **[Models API](models.md)** - Database models, mixins, and utilities

## Quick Reference

### Service Layer

WhoDis uses a hierarchical service architecture with base classes providing common functionality:

```python
from flask import current_app

# Get service from dependency injection container
ldap_service = current_app.container.get("ldap_service")

# Search for a user
result = ldap_service.search_user("john.doe@example.com")
```

**Base Classes:**
- `BaseConfigurableService` - Configuration management
- `BaseAPIService` - HTTP requests and error handling
- `BaseTokenService` - OAuth2 token management
- `BaseSearchService` - User search patterns
- `BaseCacheService` - Database caching
- `BaseAPITokenService` - Composite for API services with tokens

**Service Interfaces:**
- `ISearchService` - User search interface
- `IAuditService` - Audit logging interface
- `ICacheRepository` - Cache storage interface
- `IConfigurationService` - Configuration access interface
- `ITokenService` - Token management interface

### Model Layer

WhoDis uses SQLAlchemy models with mixins for DRY principles:

```python
from app.models.user import User

# Create a new user
user = User(email="admin@example.com", role="admin")
user.save()

# Query users
admin_users = User.query.filter_by(role="admin").all()

# Update a user
user.update(role="editor", commit=True)
```

**Base Classes:**
- `BaseModel` - Common CRUD operations
- `AuditableModel` - For audit logs and tracking
- `CacheableModel` - For cached entities
- `ServiceDataModel` - For external service data

**Mixins:**
- `TimestampMixin` - created_at/updated_at fields
- `UserTrackingMixin` - User activity tracking
- `ExpirableMixin` - Expiration management
- `SerializableMixin` - JSON serialization
- `JSONDataMixin` - JSONB additional_data storage

## Architecture Patterns

### Dependency Injection

Services are accessed through a container to enable loose coupling and testability:

```python
# In application code
from flask import current_app

# Get service from container (recommended)
service = current_app.container.get("service_name")

# Never use global imports (anti-pattern)
# from app.services.my_service import my_service  # ❌ Don't do this
```

### Interface-Based Design

Services implement interfaces for consistent APIs and testability:

```python
from app.interfaces.search_service import ISearchService
from app.services.base import BaseSearchService

class MySearchService(BaseSearchService, ISearchService):
    def search_user(self, search_term: str):
        # Implementation
        pass

    def test_connection(self) -> bool:
        # Implementation
        pass

    @property
    def service_name(self) -> str:
        return "my_service"
```

### Model Mixins

Models use mixins to avoid code duplication:

```python
from app.models.base import BaseModel, TimestampMixin, ExpirableMixin

class MyModel(BaseModel, TimestampMixin, ExpirableMixin):
    __tablename__ = "my_table"

    name = db.Column(db.String(255), nullable=False)

    # Inherits:
    # - id (from BaseModel)
    # - created_at, updated_at (from TimestampMixin)
    # - expires_at, is_expired(), extend_expiration() (from ExpirableMixin)
    # - save(), delete(), update() (from BaseModel)
```

## Common Operations

### Searching for Users

```python
# Get search orchestrator
search_orchestrator = current_app.container.get("search_orchestrator")

# Concurrent search across all services
result = search_orchestrator.search("john.doe")

# Result structure
if result.get("multiple_results"):
    # Multiple matches found
    users = result["results"]
    total = result["total"]
else:
    # Single match
    user_data = result
```

### Managing Configuration

```python
from app.services.configuration_service import config_get, config_set

# Get configuration value
ldap_host = config_get("ldap.host", "ldap.example.com")

# Set configuration value (admin only)
config_set("session.timeout", "1800")  # 30 minutes
```

### Logging Audit Events

```python
from flask import g

# Get audit service
audit_service = current_app.container.get("audit_service")

# Log a search
audit_service.log_search(
    user_email=g.user,
    search_query="john.doe",
    results_count=1,
    services_used=["ldap", "genesys"]
)

# Log an admin action
audit_service.log_admin_action(
    user_email=g.user,
    action="user_created",
    details={"new_user": "editor@example.com", "role": "editor"}
)
```

### Working with Cache

```python
from app.models.cache import SearchCache
from datetime import datetime, timezone, timedelta

# Cache a search result
cache_entry = SearchCache(
    search_query="john.doe",
    result_data={"email": "john.doe@example.com"},
    expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
)
cache_entry.save()

# Get cached result
cached = SearchCache.get_valid_cache(search_query="john.doe")
if cached:
    result = cached[0].result_data
```

## Error Handling

### Service Errors

Services use the `@handle_service_errors` decorator:

```python
from app.utils.error_handler import handle_service_errors

@handle_service_errors(raise_errors=False)
def my_service_method(self):
    # Method that may raise errors
    return risky_operation()

# With raise_errors=False: Returns None on error, logs exception
# With raise_errors=True: Re-raises exception after logging
```

### Model Validation

Models should validate data before saving:

```python
class User(BaseModel, TimestampMixin):
    email = db.Column(db.String(255), nullable=False, unique=True)
    role = db.Column(db.String(50), nullable=False)

    def validate(self):
        """Validate user data before save."""
        if not self.email or "@" not in self.email:
            raise ValueError("Invalid email address")

        if self.role not in ["viewer", "editor", "admin"]:
            raise ValueError(f"Invalid role: {self.role}")

    def save(self, commit=True):
        self.validate()
        return super().save(commit=commit)
```

## Testing

### Mocking Services

```python
# In tests
from unittest.mock import Mock

def test_search(app):
    with app.app_context():
        # Create mock service
        mock_service = Mock()
        mock_service.search_user.return_value = {"email": "test@example.com"}

        # Replace service in container
        app.container.register("ldap_service", lambda c: mock_service)

        # Test code that uses the service
        result = app.container.get("ldap_service").search_user("test")
        assert result["email"] == "test@example.com"
```

### Testing Models

```python
# In tests
def test_user_model(app, db_session):
    # Create test user
    user = User(email="test@example.com", role="viewer")
    user.save()

    # Verify save
    assert user.id is not None
    assert user.created_at is not None

    # Test update
    user.update(role="editor")
    assert user.role == "editor"

    # Test delete
    user_id = user.id
    user.delete()
    assert User.get_by_id(user_id) is None
```

## Performance Considerations

### Database Connection Pooling

WhoDis uses SQLAlchemy connection pooling:

```python
# Configured in app/database.py
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_recycle": 3600,
    "pool_pre_ping": True,
}
```

### Query Optimization

Avoid N+1 queries by using joins:

```python
# ❌ N+1 query
users = User.query.all()
for user in users:
    notes_count = user.notes.count()  # Separate query each time

# ✅ Optimized query
from sqlalchemy.orm import joinedload

users = User.query.options(joinedload(User.notes)).all()
for user in users:
    notes_count = len(user.notes)  # Already loaded
```

### Caching Strategy

- **Search results**: Cached 30 minutes (configurable)
- **API tokens**: Cached until expiration (auto-refresh)
- **Genesys data**: Cached 6 hours (groups, skills, locations)
- **Employee profiles**: Refreshed daily via scheduled job

## Security Best Practices

### Configuration Access

```python
# ✅ Good - use config_get
api_key = config_get("genesys.client_secret")

# ❌ Bad - hardcoded secrets
api_key = "hardcoded-secret-123"
```

### SQL Injection Prevention

```python
# ✅ Safe - parameterized query
User.query.filter(User.email == user_input).first()

# ❌ Unsafe - string concatenation
db.session.execute(f"SELECT * FROM users WHERE email = '{user_input}'")
```

### XSS Prevention

```python
# In templates, use proper escaping
{{ user_input|e }}  # Escapes HTML
{{ data|tojson|safe }}  # JSON encoding is safe
escapeHtml(userInput)  # JavaScript function for dynamic content
```

## Additional Resources

- **[Architecture Documentation](../architecture.md)** - System design patterns
- **[Database Documentation](../database.md)** - Schema and queries
- **[CONTRIBUTING.md](../../CONTRIBUTING.md)** - Development guidelines
- **[CLAUDE.md](../../CLAUDE.md)** - Quick reference for AI assistants

---

*Last Updated: December 29, 2025*
