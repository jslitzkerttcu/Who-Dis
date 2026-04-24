# Codebase Structure

**Analysis Date:** 2026-04-24

## Directory Layout

```
Who-Dis/
├── app/                                   # Main Flask application
│   ├── __init__.py                        # Application factory (create_app)
│   ├── container.py                       # Dependency injection container
│   ├── database.py                        # SQLAlchemy configuration and pooling
│   ├── blueprints/                        # Flask blueprints (routing)
│   │   ├── home/                          # Login, logout, index
│   │   ├── search/                        # User identity search
│   │   ├── admin/                         # Admin management
│   │   ├── session/                       # Session lifecycle
│   │   └── utilities/                     # Blocked numbers
│   ├── middleware/                        # Cross-cutting concerns
│   │   ├── auth.py                        # Main auth decorator and flow
│   │   ├── authentication_handler.py      # Azure AD header extraction
│   │   ├── role_resolver.py               # Role determination
│   │   ├── session_manager.py             # Session lifecycle
│   │   ├── user_provisioner.py            # Auto-create users on login
│   │   ├── csrf.py                        # CSRF protection
│   │   ├── audit_logger.py                # Access attempt logging
│   │   ├── security_headers.py            # Security headers
│   │   └── errors.py                      # Error handling utilities
│   ├── models/                            # SQLAlchemy ORM models
│   │   ├── base.py                        # Base classes and mixins
│   │   ├── user.py                        # User model
│   │   ├── session.py                     # UserSession model
│   │   ├── configuration.py               # Configuration model (encrypted)
│   │   ├── api_token.py                   # API token models
│   │   ├── audit.py                       # AuditLog model
│   │   ├── access.py                      # AccessAttempt model
│   │   ├── error.py                       # ErrorLog model
│   │   ├── cache.py                       # SearchCache model
│   │   ├── employee_profiles.py           # EmployeeProfiles model
│   │   ├── external_service.py            # External service config models
│   │   ├── genesys.py                     # Genesys cache models
│   │   ├── job_role_compliance.py         # Job role models
│   │   ├── user_note.py                   # UserNote model
│   │   └── __init__.py                    # Exports all models
│   ├── services/                          # Business logic and API integration
│   │   ├── base.py                        # Base service classes
│   │   ├── search_orchestrator.py         # Concurrent search coordinator
│   │   ├── result_merger.py               # Merge/deduplicate results
│   │   ├── search_enhancer.py             # Add enriched data to results
│   │   ├── ldap_service.py                # LDAP directory search
│   │   ├── genesys_service.py             # Genesys Cloud API integration
│   │   ├── graph_service.py               # Microsoft Graph API integration
│   │   ├── genesys_cache_db.py            # Genesys cache management
│   │   ├── configuration_service.py       # Encrypted config retrieval
│   │   ├── simple_config.py               # Simple config helper
│   │   ├── encryption_service.py          # Fernet encryption/decryption
│   │   ├── audit_service_postgres.py      # Audit log operations
│   │   ├── token_refresh_service.py       # Background token refresh
│   │   ├── job_role_mapping_service.py    # Job role compliance
│   │   ├── job_role_warehouse_service.py  # Job code warehouse sync
│   │   ├── compliance_checking_service.py # Compliance validation
│   │   ├── refresh_employee_profiles.py   # Employee data sync
│   │   ├── data_warehouse_service.py      # Legacy warehouse integration
│   │   └── __init__.py                    # Service imports
│   ├── interfaces/                        # Abstract service interfaces
│   │   ├── search_service.py              # ISearchService contract
│   │   ├── token_service.py               # ITokenService contract
│   │   ├── audit_service.py               # IAuditService contract
│   │   ├── cache_repository.py            # ICacheRepository contract
│   │   ├── configuration_service.py       # IConfigurationService contract
│   │   ├── external_service_repository.py # Repository pattern
│   │   ├── log_repository.py              # Log repository contract
│   │   └── __init__.py                    # Interface exports
│   ├── utils/                             # Utility functions
│   │   ├── error_handler.py               # @handle_errors decorator
│   │   ├── ip_utils.py                    # IP address parsing
│   │   ├── timezone.py                    # Timezone utilities
│   │   ├── transaction.py                 # Database transaction helpers
│   │   └── __init__.py                    # Utils imports
│   ├── templates/                         # Jinja2 HTML templates
│   │   ├── base.html                      # Base layout
│   │   ├── home/                          # Home/login pages
│   │   │   ├── index.html
│   │   │   └── login.html
│   │   ├── search/                        # Search pages
│   │   │   ├── search.html
│   │   │   └── partials/                  # HTMX fragments
│   │   ├── admin/                         # Admin pages
│   │   │   ├── index.html
│   │   │   ├── users.html
│   │   │   ├── database.html
│   │   │   ├── configuration.html
│   │   │   ├── audit_logs.html
│   │   │   ├── error_logs.html
│   │   │   ├── sessions.html
│   │   │   ├── job_role_compliance.html
│   │   │   ├── employee_profiles.html
│   │   │   ├── compliance_dashboard.html
│   │   │   └── partials/                  # Admin HTMX fragments
│   │   ├── utilities/                     # Utility pages
│   │   └── _*.html                        # Shared fragments
│   ├── static/                            # Static assets
│   │   ├── css/
│   │   │   └── style.css                  # Tailwind CSS compiled
│   │   ├── js/
│   │   │   └── blocked-numbers.js         # Form validation
│   │   └── img/                           # Favicon, product images
│   └── repositories/                      # Data access layer (if used)
├── database/                              # Database schema and scripts
│   ├── create_database.sql                # Database creation script
│   ├── create_tables.sql                  # Table schemas (auto-created on startup)
│   └── analyze_tables.sql                 # PostgreSQL ANALYZE script
├── scripts/                               # Utility and maintenance scripts
│   ├── check_config_status.py             # Display config status
│   ├── verify_encrypted_config.py         # Verify encryption key works
│   ├── diagnose_config.py                 # Diagnose config problems
│   ├── export_config.py                   # Export config as JSON
│   ├── clear_encrypted_config.py          # Wipe all encrypted config
│   ├── refresh_employee_profiles.py       # Manual employee data refresh
│   ├── verify_deployment.py               # Post-deployment health check
│   ├── drop_legacy_tables.py              # Remove old schema tables
│   ├── drop_legacy_tables.sql             # SQL for legacy cleanup
│   ├── debug/                             # Debug utilities
│   │   └── check_genesys_cache.py         # Test Genesys API/cache
│   └── archive/                           # Archived scripts
├── docs/                                  # Project documentation
│   ├── architecture.md                    # Detailed architecture guide
│   ├── database.md                        # Database setup and troubleshooting
│   ├── deployment.md                      # Deployment procedures
│   ├── job-role-compliance.md             # Job role feature documentation
│   ├── phone_number_matching.md           # Phone matching algorithm
│   ├── troubleshooting.md                 # Troubleshooting guide
│   ├── PLANNING.md                        # Project roadmap
│   ├── TASKS.md                           # Development tasks
│   ├── api/                               # API documentation
│   └── user-guide/                        # End-user documentation
├── .planning/                             # GSD planning documents
│   └── codebase/                          # This directory
│       ├── ARCHITECTURE.md                # This file
│       └── STRUCTURE.md                   # This file
├── run.py                                 # Application entry point
├── requirements.txt                       # Python dependencies
├── mypy.ini                               # Type checking configuration
├── CLAUDE.md                              # AI assistant guidance
├── README.md                              # User-facing documentation
├── CHANGELOG.md                           # Version history
├── CONTRIBUTING.md                        # Contribution guidelines
├── SECURITY.md                            # Security best practices
├── .gitignore                             # Git ignore rules
├── .env                                   # Environment variables (DO NOT COMMIT)
├── .whodis_salt                           # Encryption salt (per-installation, DO NOT COMMIT)
└── .git/                                  # Git repository
```

## Directory Purposes

**app/**
- Purpose: Main Flask application code organized by concern (blueprints, models, services)
- Contains: Python source code, HTML templates, CSS stylesheets, JavaScript
- Key files: `__init__.py` (factory), `container.py` (DI), `database.py` (ORM init)

**app/blueprints/**
- Purpose: Flask blueprints define URL routes and request handlers by feature
- Contains: Five separate modules (home, search, admin, session, utilities)
- Key files: Each blueprint's `__init__.py` registers routes and imports route handlers

**app/middleware/**
- Purpose: Cross-cutting concerns applied to requests before/after route handlers
- Contains: Authentication, authorization, session management, CSRF, error handling
- Key files: `auth.py` (main decorator flow), `authentication_handler.py` (Azure AD)

**app/models/**
- Purpose: SQLAlchemy ORM model definitions, database schema, query methods
- Contains: Base classes with mixins, concrete models for each entity
- Key files: `base.py` (mixins and BaseModel), `user.py`, `session.py`, `configuration.py`

**app/services/**
- Purpose: Business logic layer, API integration, data transformation, background jobs
- Contains: Search orchestration, identity provider clients, configuration management, encryption
- Key files: `search_orchestrator.py` (main search flow), `*_service.py` (API clients)

**app/interfaces/**
- Purpose: Abstract service interfaces for loose coupling and testing
- Contains: Python ABC (Abstract Base Class) definitions
- Key files: One interface per concern (search, audit, cache, etc.)

**app/utils/**
- Purpose: Reusable utility functions and decorators
- Contains: Error handling, IP parsing, timezone formatting, database transactions
- Key files: `error_handler.py` (@handle_errors decorator), `ip_utils.py`

**app/templates/**
- Purpose: Jinja2 HTML templates, progressively rendered server-side
- Contains: Full pages, HTMX fragments, base layout
- Key files: `base.html` (layout), blueprint-specific subdirectories

**app/static/**
- Purpose: Static assets served directly by web server
- Contains: CSS (Tailwind compiled), minimal JavaScript, images
- Key files: `css/style.css`, `js/blocked-numbers.js`

**database/**
- Purpose: Database schema definitions and initialization scripts
- Contains: SQL DDL, initialization helpers
- Key files: `create_tables.sql` (auto-executed on app startup)

**scripts/**
- Purpose: Maintenance, debugging, and administrative utilities
- Contains: Configuration management, deployment verification, data synchronization
- Key files: `verify_encrypted_config.py`, `refresh_employee_profiles.py`, `check_config_status.py`

**docs/**
- Purpose: Project documentation, guides, and architecture notes
- Contains: User guides, deployment procedures, troubleshooting
- Key files: `architecture.md`, `database.md`, `job-role-compliance.md`

## Key File Locations

**Entry Points:**
- `run.py`: Application startup (loads .env, calls create_app(), runs Flask)
- `app/__init__.py`: create_app() factory function (initializes DB, DI, blueprints)
- `app/blueprints/home/__init__.py`: Login/logout routes (first user touchpoint)

**Configuration:**
- `.env`: PostgreSQL credentials, encryption key, environment variables (DO NOT COMMIT)
- `.whodis_salt`: Encryption salt (generated per installation, DO NOT COMMIT)
- `database/create_tables.sql`: Schema definitions (DDL executed on app init)

**Core Logic:**
- `app/services/search_orchestrator.py`: Main search coordination (called by search blueprint)
- `app/middleware/auth.py`: Authentication decorator and flow (applied to all protected routes)
- `app/container.py`: Service registration and dependency resolution

**Authentication & Authorization:**
- `app/middleware/authentication_handler.py`: Azure AD header extraction
- `app/middleware/role_resolver.py`: Role lookup in database
- `app/models/user.py`: User model with role constants
- `app/blueprints/home/__init__.py`: Login route

**Database:**
- `app/database.py`: SQLAlchemy configuration, connection pooling
- `app/models/`: ORM model definitions
- `database/create_tables.sql`: Schema (loaded by app/__init__.py)

**Search Feature:**
- `app/blueprints/search/__init__.py`: Route handlers for `/search` and `/api/search`
- `app/services/search_orchestrator.py`: Parallel search coordinator
- `app/services/ldap_service.py`, `genesys_service.py`, `graph_service.py`: API clients
- `app/services/result_merger.py`: Merge and deduplicate results
- `app/templates/search/`: Search page and fragments

**Admin Feature:**
- `app/blueprints/admin/__init__.py`: Route registration (delegates to submodules)
- `app/blueprints/admin/users.py`: User management routes
- `app/blueprints/admin/database.py`: Database health, cache, audit routes
- `app/blueprints/admin/config.py`: Configuration editor routes
- `app/templates/admin/`: Admin pages

**Session Management:**
- `app/models/session.py`: UserSession model with timeout logic
- `app/blueprints/session/__init__.py`: `/api/session/check`, `/api/session/extend` routes
- `app/middleware/session_manager.py`: Session creation and expiration checks

**Error Handling:**
- `app/utils/error_handler.py`: @handle_errors decorator for routes, @handle_service_errors for services
- `app/models/error.py`: ErrorLog model for storing stack traces
- Global error handlers in `app/__init__.py` (404, 500)

**Testing:**
- No test framework currently configured; tests would go in `tests/` or use pytest markers

## Naming Conventions

**Files:**
- Blueprint modules: `__init__.py` (routes), `{feature_name}.py` (handlers)
- Service files: `{service_name}_service.py` (e.g., `ldap_service.py`)
- Model files: `{entity_name}.py` (singular, e.g., `user.py` not `users.py`)
- Interface files: `{interface_name}_service.py` or `{interface_name}.py`
- Template files: `{feature_name}.html` for full pages, `_{partial_name}.html` for fragments
- Scripts: `{action}_{noun}.py` (e.g., `refresh_employee_profiles.py`)

**Directories:**
- Feature blueprints: lowercase plural or feature name (e.g., `search`, `admin`, `utilities`)
- Models directory: `models/` (singular namespace, contains multiple files)
- Services directory: `services/` (plural, contains service implementations)
- Interfaces directory: `interfaces/` (plural, contains abstract classes)
- Middleware directory: `middleware/` (plural, contains cross-cutting concerns)
- Templates directory: `templates/` with subdirectories matching blueprint names

**Classes:**
- Model classes: PascalCase, singular (e.g., `User`, `UserSession`, `AuditLog`)
- Service classes: PascalCase + "Service" suffix (e.g., `LDAPService`, `SearchOrchestrator`)
- Interface classes: PascalCase + "I" prefix (e.g., `ISearchService`)
- Mixin classes: PascalCase + "Mixin" suffix (e.g., `TimestampMixin`)
- Container class: `ServiceContainer`

**Functions & Methods:**
- Route handlers: `lowercase_with_underscores` (e.g., `manage_users`, `execute_search`)
- Private methods: `_leading_underscore` (e.g., `_get_config`, `_make_request`)
- Config keys: `lowercase.with.dots` for namespace (e.g., `search.ldap_timeout`)
- Database columns: `lowercase_with_underscores` (e.g., `user_email`, `created_at`)

**Constants:**
- All caps with underscores (e.g., `ROLE_VIEWER`, `ROLE_ADMIN`)
- Environment variables: ALL_CAPS (e.g., `POSTGRES_HOST`, `WHODIS_ENCRYPTION_KEY`)

## Where to Add New Code

**New Feature:**
- **Primary code**: Create new blueprint in `app/blueprints/{feature_name}/`
  - Routes in `__init__.py` or imported from submodules
  - Handlers in `{feature_name}.py` or role-specific files
- **Tests**: Create `tests/{feature_name}_test.py` (once testing framework added)
- **Templates**: Create `app/templates/{feature_name}/` with `base.html` and `partials/`

**New Service/Business Logic:**
- **Implementation**: Create `app/services/{service_name}_service.py`
  - Extend `BaseConfigurableService` or `BaseAPIService` if applicable
  - Implement relevant interfaces from `app/interfaces/`
- **Interface (if needed)**: Create `app/interfaces/{service_name}.py` with ABC
- **Registration**: Add factory to `register_services()` in `app/container.py`
  - Example: `container.register("my_service", lambda c: MyService())`

**New Database Entity:**
- **Model**: Create `app/models/{entity_name}.py`
  - Extend `BaseModel` and relevant mixins from `app/models/base.py`
  - Define columns, relationships, and query methods
- **Export**: Add to `app/models/__init__.py`
- **Schema**: Update `database/create_tables.sql` with DDL
- **Statistics**: Run `ANALYZE {table_name}` after first data insertion

**New Route (in existing blueprint):**
- **Definition**: Add to blueprint module (e.g., `app/blueprints/admin/config.py`)
  - Apply `@admin_bp.route()`, `@require_role()` decorators
  - Use `@handle_errors` for error handling
- **Template**: Create in `app/templates/{blueprint_name}/` or `partials/`
- **Helper**: Extract reusable logic to service layer

**Configuration Value:**
- **Storage**: Add via admin UI or run script (`python scripts/export_config.py`)
  - Category: dot-separated namespace (e.g., `genesys.api_timeout`)
  - Value: encrypted before storage
- **Retrieval**: Call `config_get("category.key", default_value)` in route/service
  - Automatically decrypted and cached in memory

**Utilities & Helpers:**
- **Location**: `app/utils/{utility_name}.py` for general utilities
- **Pattern**: Pure functions or decorator classes
- **Reusability**: Avoid duplicating logic; extract to utils if used in 2+ places

## Special Directories

**app/repositories/**
- Purpose: Data access abstraction (if using Repository pattern)
- Generated: No (optional refactoring target)
- Committed: Would be committed if added

**.planning/codebase/**
- Purpose: GSD analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes (by gsd-map-codebase command)
- Committed: Yes (helps future Claude instances navigate codebase)

**scripts/archive/**
- Purpose: Legacy scripts no longer in active use
- Generated: No (manual organization)
- Committed: Yes (preserved for historical reference)

**scripts/debug/**
- Purpose: Debugging utilities for troubleshooting specific issues
- Generated: No (developer created)
- Committed: Yes (useful for ops/debugging)

**.auto-claude/**
- Purpose: Auto-sync directory for continuous integration
- Generated: Yes (by CI/CD system)
- Committed: No (.gitignored)

**.ruff_cache/**
- Purpose: Ruff linter cache
- Generated: Yes (by ruff formatter/linter)
- Committed: No (.gitignored)

**.git/**
- Purpose: Git version control metadata
- Generated: Yes (by git init)
- Committed: Not needed (git internal)
