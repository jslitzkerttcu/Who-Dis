# WhoDis Architecture Documentation

This document provides detailed architectural information for developers working on the WhoDis codebase.

## Table of Contents
- [Dependency Injection Container](#dependency-injection-container)
- [Model Hierarchy](#model-hierarchy)
- [Service Layer](#service-layer)
- [Repository Pattern](#repository-pattern)
- [Search Architecture](#search-architecture)
- [Middleware Pipeline](#middleware-pipeline)

## Dependency Injection Container

WhoDis uses a custom dependency injection container for managing service lifecycle and dependencies.

### Container Pattern (`app/container.py`)

**Key Features:**
- Thread-safe singleton container with lazy service instantiation
- Factory-based registration for deferred creation
- Interface-based service discovery with `get_all_by_interface()`
- Automatic dependency resolution through factory closures

**Service Registration** (`inject_dependencies()`):
```python
# All services registered at application startup
def register_services(container: ServiceContainer) -> None:
    container.register("ldap_service", lambda c: LDAPService())
    container.register("genesys_service", lambda c: GenesysCloudService())
    # ... more services
```

**Service Retrieval:**
```python
# By name
ldap_service = current_app.container.get("ldap_service")

# By interface
search_services = current_app.container.get_all_by_interface(ISearchService)
```

**Benefits:**
- Loose coupling between components
- Easy testing with mock services
- Clear dependency graph
- Thread-safe singleton management

## Model Hierarchy

### Base Classes (`app/models/base.py`)

**BaseModel**: Common CRUD operations
```python
class BaseModel:
    def save() -> Self
    def update(**kwargs) -> None
    def delete() -> None
    @classmethod get_by_id(id) -> Optional[Self]
```

**Mixins:**
- `TimestampMixin`: Provides `created_at`/`updated_at`
- `UserTrackingMixin`: Provides `user_email`/`ip_address`/`user_agent`/`session_id`
- `ExpirableMixin`: Provides `expires_at` and expiration management
- `JSONDataMixin`: Provides JSONB `data` field with helper methods

**Composite Base Classes:**
- `AuditableModel`: BaseModel + TimestampMixin + UserTrackingMixin + JSONDataMixin
- `CacheableModel`: BaseModel + ExpirableMixin (for cache entries)
- `ServiceDataModel`: BaseModel + TimestampMixin + JSONDataMixin (for external service data)

### Model Catalog

**Core Models:**
- `User`: User management with roles (BaseModel + TimestampMixin)
- `Configuration`: Encrypted configuration storage (BaseModel)
- `ApiToken`: API token storage with expiration (BaseModel + ExpirableMixin)
- `Session`: User session management (BaseModel + ExpirableMixin)

**Logging Models:**
- `AuditLog`: Audit log entries (AuditableModel)
- `AccessAttempt`: Access tracking (AuditableModel)
- `ErrorLog`: Error logging (AuditableModel)

**Cache Models:**
- `SearchCache`: Search result caching (CacheableModel)
- `GenesysGroup`, `GenesysLocation`, `GenesysSkill`: Genesys cache (ServiceDataModel)
- `EmployeeProfile`: Consolidated employee data with photos (BaseModel + TimestampMixin)

**Feature Models:**
- `UserNote`: Internal notes about users (BaseModel + TimestampMixin)
- `JobCode`, `SystemRole`, `JobRoleMapping`: Job role compliance (BaseModel + TimestampMixin)
- `ExternalService`: External service tracking (BaseModel + TimestampMixin)

## Service Layer

### Base Service Classes (`app/services/base.py`)

**Hierarchy:**
```
BaseConfigurableService (configuration access)
  ├── BaseAPIService (HTTP requests + error handling)
  │     └── BaseTokenService (OAuth2 token management)
  │           └── BaseAPITokenService (composite for API services)
  ├── BaseSearchService (user search functionality)
  └── BaseCacheService (database caching patterns)
```

### Service Catalog

**Identity Providers:**
- `LDAPService`: Active Directory/LDAP integration (extends BaseSearchService)
- `GenesysCloudService`: Genesys Cloud API (extends BaseAPITokenService)
- `GraphService`: Microsoft Graph API beta (extends BaseAPITokenService)

**Search Coordination:**
- `SearchOrchestrator`: Coordinates concurrent searches across LDAP, Graph, Genesys
- `ResultMerger`: Merges search results with intelligent data prioritization
- `SearchEnhancer`: Enhances results with employee profile data

**Infrastructure:**
- `ConfigurationService`: Simplified configuration access (wraps SimpleConfig)
- `SimpleConfig`: Core configuration with encryption support
- `EncryptionService`: Fernet-based encryption utilities
- `AuditServicePostgres`: PostgreSQL-based audit logging
- `TokenRefreshService`: Background service for automatic API token renewal

**Caching:**
- `GenesysCacheDB`: PostgreSQL caching for Genesys groups, skills, locations
- `RefreshEmployeeProfiles`: Consolidated employee data service

**Job Role Compliance:**
- `JobRoleMappingService`: CRUD operations for job role mappings
- `JobRoleWarehouseService`: Integration with data warehouse via pyodbc
- `ComplianceCheckingService`: Validates user compliance against expected roles

## Repository Pattern

WhoDis uses the repository pattern to abstract data access for testability and maintainability.

### Interfaces (`app/interfaces/`)

- `ISearchService`: Interface for search implementations
- `ICacheRepository`: Interface for cache storage operations
- `IAuditService`: Interface for audit logging
- `IConfigurationService`: Interface for configuration access
- `ITokenService`: Interface for token management

### Implementations (`app/repositories/`)

- `CacheRepository`: PostgreSQL implementation of cache storage
- `ExternalServiceRepository`: External service data persistence
- `LogRepository`: Centralized logging repository

### Usage Pattern

```python
# Services implement interfaces
class LDAPService(BaseSearchService, ISearchService):
    def search_user(self, term: str) -> Optional[Dict[str, Any]]:
        # Implementation
        pass

# Access through container
search_service = current_app.container.get("ldap_service")
result = search_service.search_user("john.doe")
```

## Search Architecture

WhoDis implements a sophisticated multi-service search system with three layers: orchestration, merging, and enhancement.

### Layer 1: Search Orchestrator (`search_orchestrator.py`)

**Purpose:** Coordinates concurrent searches across multiple identity providers

**Key Features:**
- Uses `ThreadPoolExecutor` to search LDAP, Genesys, and Graph simultaneously
- Configurable timeouts per service (LDAP: 3s, Graph: 4s, Genesys: 5s, Overall: 8s)
- Error isolation: Service failures don't block other services
- Proper future cancellation on timeout to prevent resource leaks
- Flask request context preserved with `copy_current_request_context()`

**Flow:**
```python
def execute_concurrent_search(search_term):
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit searches concurrently
        ldap_future = executor.submit(ldap_service.search_user, search_term)
        genesys_future = executor.submit(genesys_service.search_user, search_term)
        graph_future = executor.submit(graph_service.search_user, search_term)

        # Process results with timeout handling
        ldap_result = ldap_future.result(timeout=3)
        # ... process other results

    return ldap_result, genesys_result, graph_result
```

### Layer 2: Result Merger (`result_merger.py`)

**Purpose:** Intelligently combines data from multiple sources

**Key Features:**
- Graph API data takes precedence over LDAP for enhanced fields
- Field-level merging with configurable priority rules
- Email-based correlation across systems
- Conflict resolution for duplicate data

**Priority Rules:**
- Password fields: LDAP data prioritized
- Enhanced fields (hire date, etc.): Graph data prioritized
- Phone numbers: Tagged by source (Genesys/Teams/Legacy)

### Layer 3: Search Enhancer (`search_enhancer.py`)

**Purpose:** Enriches results with additional cached data

**Key Features:**
- Employee profile integration from consolidated cache
- Photo loading strategy: lazy (default) or eager based on config
- Adds warehouse data and historical information

### Complete Search Flow

1. User submits search term via HTMX request
2. `SearchOrchestrator` dispatches concurrent searches to LDAP, Graph, and Genesys
3. Each service returns results or `multiple_results` with timeout protection
4. `ResultMerger` combines LDAP and Graph data with intelligent prioritization
5. `SearchEnhancer` adds employee profile data and photos
6. Results cached in PostgreSQL with 30-minute expiration
7. HTML fragment returned to browser for seamless HTMX update

## Middleware Pipeline

WhoDis uses a comprehensive middleware pipeline for cross-cutting concerns.

### Middleware Components (`app/middleware/`)

**Execution Order:**
1. `security_headers.py`: Add security headers (CSP, X-Frame-Options, etc.)
2. `authentication_handler.py`: Extract Azure AD principal from headers
3. `role_resolver.py`: Determine user role from database/config
4. `user_provisioner.py`: Auto-provision user on first login
5. `session_manager.py`: Session lifecycle and timeout management
6. `csrf.py`: CSRF protection for state-changing operations
7. `auth.py`: Role-based authentication orchestration
8. `audit_logger.py`: Automatic audit logging for requests
9. `errors.py`: Global error handling and logging

### Authentication Flow

```
Request → Security Headers
       → Authentication Handler (extract X-MS-CLIENT-PRINCIPAL-NAME)
       → Role Resolver (check database users table)
       → User Provisioner (create user if new)
       → Session Manager (validate/extend session)
       → CSRF Protection (for POST/PUT/DELETE)
       → Route Handler (@auth_required, @require_role decorators)
       → Audit Logger (log access attempt)
       → Error Handler (catch exceptions)
       → Response
```

### Key Decorators

```python
@auth_required
def my_route():
    # User is authenticated, g.user contains email
    pass

@require_role("admin")
def admin_route():
    # User must have admin role
    pass
```

## Architectural Patterns Used

1. **Dependency Injection**: Container-based service management
2. **Repository Pattern**: Data access abstraction through interfaces
3. **Factory Pattern**: Service creation via registered factories
4. **Decorator Pattern**: `@handle_service_errors`, `@auth_required`, `@require_role`
5. **Template Method**: Base classes define patterns, subclasses implement specifics
6. **Observer Pattern**: Middleware observes all requests
7. **Strategy Pattern**: Multiple search services implement `ISearchService`

## References

- [Job Role Compliance Architecture](job-role-compliance.md)
- [Database Documentation](database.md)
- [Project Planning](PLANNING.md)
