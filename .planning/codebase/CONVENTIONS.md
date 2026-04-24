# Coding Conventions

**Analysis Date:** 2026-04-24

## Naming Patterns

**Files:**
- Modules use `snake_case`: `authentication_handler.py`, `search_orchestrator.py`, `user_provisioner.py`
- Blueprints in subdirectories: `app/blueprints/{feature}/__init__.py` contains blueprint routes
- Services in dedicated files: `app/services/{service_name}.py`
- Models in dedicated files: `app/models/{model_name}.py`
- Interfaces in `app/interfaces/`: `{service_type}.py` (e.g., `search_service.py`, `cache_repository.py`)

**Functions:**
- Public methods use `snake_case`: `search_user()`, `get_or_create()`, `update_last_login()`
- Private methods prefixed with `_`: `_get_config()`, `_normalize_search_term()`, `_make_request()`
- Decorators prefixed with `@`: `@auth_required`, `@require_role()`, `@handle_errors`, `@abstractmethod`
- Helper/utility functions in separate modules: `app/utils/error_handler.py`, `app/utils/ip_utils.py`

**Variables:**
- Use `snake_case` for all variables: `user_email`, `cache_key`, `search_term`, `service_name`
- Private instance variables prefixed with `_`: `self._config_cache`, `self._base_url`, `self._token_service_name`
- Constants in `UPPER_CASE`: `ROLE_VIEWER = "viewer"`, `ROLE_ADMIN = "admin"`
- Class constants for enums: `User.ROLE_VIEWER`, `User.ROLE_EDITOR`

**Types:**
- Class names use `PascalCase`: `BaseModel`, `SearchOrchestrator`, `AuthenticationHandler`
- Interface/Abstract classes prefixed with `I`: `ISearchService`, `ICacheRepository`, `IConfigurationService`
- Model classes named singularly: `User`, `UserNote`, `ApiToken`, `ErrorLog`
- Mixin classes suffixed with `Mixin`: `TimestampMixin`, `UserTrackingMixin`, `ExpirableMixin`, `JSONDataMixin`

## Code Style

**Formatting:**
- Black-compatible formatting (no explicit config, but follows Python standard)
- 4-space indentation throughout
- Line length is not strictly enforced but kept reasonable (80-120 chars typical)
- Double quotes for strings: `"string"` preferred over `'string'`

**Linting:**
- Tool: `ruff` (in requirements.txt, no config file)
- Run: `ruff check --fix`
- Type checking: `mypy` with config at `mypy.ini`
- Run: `mypy app/ scripts/`

**Mypy Configuration:**
- Located at: `mypy.ini`
- Settings: `python_version = 3.8`, `warn_return_any = True`
- Ignores third-party library stubs: `ldap3`, `msal`, `flask_sqlalchemy`, `sqlalchemy`, `dotenv`, `httpx`
- Special handling for `app.models` and `app.database` (allows implicit optionals for SQLAlchemy)

## Import Organization

**Order:**
1. Standard library imports: `import os`, `import logging`, `from datetime import datetime`, `from typing import Optional`
2. Third-party library imports: `from flask import Flask, g, request`, `from sqlalchemy import event`, `import requests`
3. Local app imports: `from app.models.base import BaseModel`, `from app.services.configuration_service import config_get`

**Path Aliases:**
- No path aliases configured; use absolute imports from `app/` root
- Example: `from app.models.user import User` (not relative imports)

**Barrel Files:**
- Blueprint __init__.py files contain routes: `app/blueprints/admin/__init__.py`
- Model imports in selective __init__.py files: `from app.models import ErrorLog` works via explicit imports

## Error Handling

**Patterns:**
- Decorator-based: `@handle_errors` for routes, `@handle_service_errors` for services
- Located in: `app/utils/error_handler.py`
- Route handler signature:
  ```python
  @handle_errors  # Uses defaults for HTML responses
  @handle_errors(json_response=True)  # For API endpoints
  @handle_errors(error_template="admin/error.html", log_errors=True, audit_errors=True)
  def my_route():
      # Route logic
  ```
- Service method signature:
  ```python
  @handle_service_errors(raise_errors=True)  # Re-raise after logging
  @handle_service_errors(raise_errors=False, default_return={})  # Return value on error
  def my_service_method(self):
      # Service logic
  ```

**Exception Mapping:**
- `ValueError` → HTTP 400
- `PermissionError` → HTTP 403
- `FileNotFoundError` → HTTP 404
- `SQLAlchemyError` → HTTP 500 with generic "Database error occurred"
- All others → HTTP 500

**Logging Pattern:**
- Use module-level logger: `logger = logging.getLogger(__name__)`
- Log levels:
  - `logger.debug()` for detailed flow information
  - `logger.info()` for significant events
  - `logger.warning()` for recoverable issues
  - `logger.error()` for failures, with `exc_info=True` for tracebacks
- Example: `logger.error(f"Error in {service}.{method}: {str(e)}", exc_info=True)`

## Logging

**Framework:** Python's built-in `logging` module

**Patterns:**
- Module logger initialization: `logger = logging.getLogger(__name__)` at module top
- Service loggers: Include service name in log messages for traceability
- Audit logging: Use `audit_service.log_error()` for error tracking with user context
- Sensitive data redaction: Request data sanitized before logging (passwords, tokens)

**When/How to Log:**
- Request entry points: Log HTTP method, URL, user
- API calls: Log `logger.debug()` for request, `logger.debug()` for response status
- Errors: Always use `logger.error(..., exc_info=True)` with full traceback
- Timing: Log start/completion for long operations (cache refresh, bulk operations)
- Configuration: Log config load success/failure at startup

## Comments

**When to Comment:**
- Complex business logic: Document the "why", not the "what"
- Non-obvious algorithmic choices: Explain rationale
- Workarounds: Mark with `# NOTE:` or `# HACK:` when working around known issues
- Integration points: Comment when interfacing with external APIs

**JSDoc/TSDoc:**
- Not used (Python codebase)
- Docstrings used instead: Follow Google/NumPy style
- Module docstrings: First line is brief description
- Function docstrings: Brief summary, Args, Returns, optional Raises
- Example from `app/models/base.py`:
  ```python
  def cleanup_expired(cls, commit=True):
      """Remove all expired records for this model.

      Args:
          commit: Whether to commit the transaction. Default True.

      Returns:
          Number of expired records deleted.
      """
  ```

**Docstring Usage:**
- Mandatory for: Public APIs, service methods, interfaces, decorators
- Optional for: Internal helper functions, simple getters
- Location: Immediately after function/class definition

## Function Design

**Size:** 
- Typical service methods: 20-40 lines
- Longer methods: 50-100 lines acceptable for complex orchestration
- Guideline: If exceeds 100 lines, consider extracting helper methods
- Example: `search_orchestrator.search()` = 80 lines combining multiple steps

**Parameters:**
- Explicit parameters over kwargs: `def search_user(self, search_term: str)`
- Type hints for all public methods: `search_term: str`, `commit: bool = True`
- Optional params with defaults: `cache_repository: Optional[ICacheRepository] = None`
- Maximum reasonable params: 4-5; use objects for more complex signatures

**Return Values:**
- Explicit type hints: `-> Optional[Dict[str, Any]]`, `-> bool`, `-> List[User]`
- Consistent return types: Don't return either list or single object; use multiple_results wrapper
- Single responsibility: Return one logical result, not multiple unrelated values
- Pattern from `BaseSearchService`: Return `Optional[Dict]` with possible `multiple_results` flag

## Module Design

**Exports:**
- Explicit imports in blueprints: `from app.models import User` works if models/__init__.py exports
- Service classes exported as singletons or via container: `from app.services.genesys_service import genesys_service`
- Interfaces imported directly: `from app.interfaces.search_service import ISearchService`

**Barrel Files:**
- Used selectively in `app/blueprints/{name}/__init__.py` (contains blueprint + routes)
- Not used for services or models (import directly)
- Example: `app/models/__init__.py` may not exist; import `from app.models.user import User` directly

**Circular Import Prevention:**
- Local imports inside functions when needed: `from app.models.session import UserSession`
- Service container accessed via `current_app.container.get()` to avoid circular deps
- Interfaces used as type hints to decouple dependencies

**Class Composition:**
- Mixins for code reuse: `class User(BaseModel, TimestampMixin)` combines behaviors
- Base classes for common patterns: `BaseAPIService`, `BaseTokenService`, `BaseSearchService`
- Multiple inheritance pattern: `BaseAPITokenService(BaseTokenService, BaseSearchService)` for combined functionality

## Configuration Access

**Pattern:**
- Import function: `from app.services.configuration_service import config_get`
- Usage: `config_get("category.key", "default_value")`
- Never hardcode secrets; always use config_get
- Example: `ldap_server = config_get("ldap.server", "localhost")`

**In Base Classes:**
- Override in __init__: `self._config_prefix = "service_name"`
- Retrieve in methods: `self._get_config("key", "default")`
- Caching built-in: `self._config_cache` dict prevents repeated lookups

## Decorator Patterns

**Authentication:**
- Use `@auth_required` on all protected routes
- Combine with `@require_role("admin")` or `@require_role("viewer")`
- Location: `app/middleware/auth.py`
- Pattern: Always on top of function stack

**Error Handling:**
- `@handle_errors` for routes (returns HTML or JSON)
- `@handle_service_errors` for service methods (logs and re-raises or returns default)

**Database Transactions:**
- No explicit decorator; use model save(commit=True/False)
- Batch operations: Set commit=False, then call db.session.commit() once

---

*Convention analysis: 2026-04-24*
