# External Integrations

**Analysis Date:** 2026-04-24

## APIs & External Services

**Active Directory / LDAP:**
- LDAP (Lightweight Directory Access Protocol) - Employee directory search
  - SDK/Client: ldap3 2.9.1
  - Configuration: ldap.host, ldap.port, ldap.use_ssl, ldap.bind_dn, ldap.bind_password, ldap.base_dn
  - Service: `app/services/ldap_service.py` (LDAPService class)
  - Timeout: Configurable via ldap.connect_timeout, ldap.operation_timeout

**Microsoft Graph API:**
- Microsoft Graph - User profiles, photos, organizational data
  - SDK/Client: msal 1.34.0 + requests 2.33.0
  - Auth: OAuth2 client credentials flow (tenant-based)
  - Service: `app/services/graph_service.py` (GraphService class)
  - Configuration: graph.client_id, graph.client_secret, graph.tenant_id
  - Scope: https://graph.microsoft.com/.default
  - Endpoints: https://graph.microsoft.com/beta
  - Token Storage: ApiToken model with service_name='microsoft_graph'

**Genesys Cloud:**
- Genesys Cloud - Contact center data, phone numbers, skills, groups
  - SDK/Client: requests 2.33.0 (OAuth2 client credentials)
  - Auth: Client credentials flow with region-specific endpoints
  - Service: `app/services/genesys_service.py` (GenesysCloudService class)
  - Configuration: genesys.client_id, genesys.client_secret, genesys.region
  - Base URL: https://api.{region} (region from mypurecloud.com to apne3.pure.cloud)
  - Token URL: https://{auth_domain}/oauth/token (region-specific mapping)
  - Token Storage: ApiToken model with service_name='genesys'
  - Cache: GenesysCacheDB (`app/services/genesys_cache_db.py`) with periodic refresh

**Azure AD Header Authentication:**
- Azure AD SSO - User authentication via request headers
  - Method: X-MS-CLIENT-PRINCIPAL-NAME header (passed by Azure App Service / proxy)
  - Handler: `app/middleware/authentication_handler.py` (AuthenticationHandler class)
  - Configuration: Via reverse proxy or Azure App Service authentication module
  - Basic auth: Disabled for security

## Data Storage

**Databases:**
- PostgreSQL 12+ (primary, required for production)
  - Connection: Via psycopg2-binary 2.9.11
  - Client: SQLAlchemy 2.0.45 ORM
  - URI: postgresql://{user}:{password}@{host}:{port}/{database}
  - Environment vars: POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
  - Connection pooling: QueuePool with size=10, max_overflow=20, recycle=3600s
  - Tables: Configuration, ApiToken, User, AuditLog, ErrorLog, UserSession, EmployeeProfile, Genesys* cache tables

- SQLite (fallback only, not recommended for production)
  - Fallback URI: sqlite:///logs/app.db
  - Used if PostgreSQL connection fails at startup

**File Storage:**
- Local filesystem only (profile photos cached in PostgreSQL database)
- Photo data stored as BYTEA in employee_profiles table
- No cloud storage integration (AWS S3, Azure Blob, etc.)

**Caching:**
- PostgreSQL-based cache tables:
  - `employee_profiles` - Consolidated user data with photos
  - `genesys_groups`, `genesys_skills`, `genesys_users`, `genesys_organizations` - Genesys cache
- In-memory service caches: Configuration service (dict-based with manual clear)
- Cache refresh: Periodic background service for token and Genesys data

## Authentication & Identity

**Auth Provider:**
- Azure AD (Microsoft Entra ID) via OAuth2
  - Mechanism: X-MS-CLIENT-PRINCIPAL-NAME header (requires Azure App Service or proxy)
  - Implementation: Custom header-based authentication
  - Handler: `app/middleware/authentication_handler.py`
  - Fallback: None (basic auth removed for security)

**Role-Based Access Control:**
- Database-stored user roles (viewer, editor, admin)
- Role determination: `app/middleware/role_resolver.py`
- Stored in: users.role column (database model)
- Enforced via: `@auth_required` and `@require_role(role_name)` decorators

## Monitoring & Observability

**Error Tracking:**
- Database-based error logging (no external service)
  - Model: ErrorLog (`app/models/error.py`)
  - Service: PostgresAuditService (`app/services/audit_service_postgres.py`)
  - Decorator: `@handle_service_errors` for automatic logging

**Logs:**
- Python logging framework (level: INFO)
- Format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
- Destinations: Console output, Flask app logger
- Audit trail: PostgreSQL audit_log table with full event tracking

**Audit Logging:**
- Service: PostgresAuditService (`app/services/audit_service_postgres.py`)
- Events logged: Searches, access attempts, admin actions, config changes, errors
- Storage: audit_log and access_attempt tables
- User tracking: email, IP address, user agent, session ID

## CI/CD & Deployment

**Hosting:**
- Azure App Service (primary recommendation per CLAUDE.md)
- Alternative: Ubuntu server with Gunicorn + Nginx
- Docker: Supported via Dockerfile (referenced in deployment guide)

**CI Pipeline:**
- None detected in repository
- Quality commands available: `ruff check --fix`, `ruff format .`, `mypy app/ scripts/`

## Environment Configuration

**Required env vars:**
- POSTGRES_HOST - PostgreSQL hostname/IP
- POSTGRES_PORT - PostgreSQL port (default 5432)
- POSTGRES_DB - Database name (whodis_db)
- POSTGRES_USER - Database user (whodis_user)
- POSTGRES_PASSWORD - Database password (required, no default)
- WHODIS_ENCRYPTION_KEY - Fernet encryption key for configuration (required)

**Optional env vars:**
- FLASK_ENV - Development/production (sets debug mode)
- PYTHONPATH - Python module search path (if needed)

**Secrets location:**
- .env file (local development, not committed)
- Environment variables (production deployment)
- Encrypted configuration table (database-stored after initial setup)

**Configuration Bootstrap:**
- Initial app configuration via Configuration table with encryption
- API credentials encrypted with WHODIS_ENCRYPTION_KEY
- Configuration service auto-decrypts values on retrieval

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- None detected (read-only search platform)

## Background Services

**Token Refresh:**
- Service: TokenRefreshService (`app/services/token_refresh_service.py`)
- Frequency: Periodic checks, tokens refreshed before expiration
- Services refreshed: Microsoft Graph, Genesys Cloud
- Start: Automatic on Flask app startup (WERKZEUG_RUN_MAIN check)

**Genesys Cache Refresh:**
- Service: GenesysCacheDB (`app/services/genesys_cache_db.py`)
- Frequency: Configurable via database configuration
- Data refreshed: Groups, skills, users, organizations
- Triggered: On startup if needed, periodic via background service

**Session Cleanup:**
- Model: UserSession (`app/models/session.py`)
- Task: cleanup_expired() called on startup
- Removes: Expired sessions based on timeout configuration

## API Integration Details

**Search Architecture:**
- SearchOrchestrator (`app/services/search_orchestrator.py`) - Parallel search across all services
- Concurrent execution: ThreadPoolExecutor with configurable workers
- Timeout protection: Individual service timeouts + overall timeout
- Result merging: ResultMerger (`app/services/result_merger.py`) - Matches users across systems
- Result enhancement: SearchEnhancer (`app/services/search_enhancer.py`) - Augments with cached data

**Rate Limiting:**
- Per-service timeout configuration (ldap.operation_timeout, graph timeout, etc.)
- No external rate limiting (internal timeout-based limiting)

---

*Integration audit: 2026-04-24*
