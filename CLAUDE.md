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

### Dependencies
Key dependencies in requirements.txt:
```
Flask==3.0.0                 # Web framework
Flask-SQLAlchemy==3.1.1      # Database ORM
psycopg2-binary==2.9.10      # PostgreSQL adapter
requests==2.31.0             # HTTP client for API integrations
msal==1.24.1                 # Microsoft Graph authentication
ldap3==2.9.1                 # LDAP/Active Directory integration
cryptography==42.0.5         # Encryption for sensitive data
pytz==2024.1                 # Timezone handling for token expiration
tabulate==0.9.0              # Table formatting for CLI tools
pyodbc==5.2.0                # SQL Server connectivity for data warehouse
ruff                         # Python linting
mypy                         # Type checking
```

Frontend dependencies are delivered via CDN:
- **HTMX**: Dynamic content updates and AJAX interactions
- **Tailwind CSS**: Utility-first CSS framework for styling
- **FontAwesome**: Icon library for visual elements

### Database Management
```bash
# Check configuration status
python scripts/check_config_status.py

# Verify encrypted configuration
python scripts/verify_encrypted_config.py

# Diagnose configuration problems
python scripts/diagnose_config.py

# Export configuration for backup
python scripts/export_config.py

# Test Genesys cache functionality
python scripts/check_genesys_cache.py

# Test Genesys locations cache (manual)
python scripts/test_locations_cache.py

# Refresh employee profiles (consolidated data)
python scripts/refresh_employee_profiles.py refresh

# Drop legacy tables (for migrations from pre-2.0)
python scripts/drop_legacy_tables.py --dry-run  # Preview changes
python scripts/drop_legacy_tables.py            # Execute migration

# Verify deployment after migration
python scripts/verify_deployment.py
```

## Architecture

### Application Structure
WhoDis is a Flask-based identity lookup service with PostgreSQL backend and integrated search across multiple identity providers using a modern hybrid server-side + HTMX architecture:

- **`app/__init__.py`**: Application factory that initializes Flask, database, configuration service, and registers blueprints
- **`app/database.py`**: Database configuration and connection management
- **`app/blueprints/`**: Contains four main blueprints:
  - `home`: Landing page with product branding and login interface
  - `search`: Identity search interface with real-time results (requires 'viewer' role minimum)
  - `admin`: Admin panel with user management, configuration editor, and audit logs (requires 'admin' role)
  - `session`: Session management endpoints for timeout tracking and extension
- **`app/middleware/auth.py`**: Implements role-based authentication with database users, encrypted config fallback, and basic auth
- **`app/models/`**: SQLAlchemy models with base class hierarchy:
  - **Base Classes** (`base.py`):
    - `BaseModel`: Common CRUD operations
    - `TimestampMixin`: Provides created_at/updated_at
    - `UserTrackingMixin`: Provides user_email/ip_address/user_agent/session_id
    - `ExpirableMixin`: Provides expires_at and expiration management
    - `AuditableModel`: Combines timestamps, user tracking, and JSON data
    - `CacheableModel`: For cache entries with expiration
    - `ServiceDataModel`: For external service data
  - **Models** (consolidated architecture):
    - `user.py`: User management with roles (extends BaseModel + TimestampMixin)
    - `configuration.py`: Encrypted configuration storage (extends BaseModel)
    - `audit.py`: Audit log entries in `audit_log` table (extends AuditableModel)
    - `access.py`: Access attempt tracking in `access_attempts` table (extends AuditableModel)
    - `error.py`: Error logging in `error_log` table (extends AuditableModel)
    - `api_token.py`: API token storage with expiration (extends BaseModel + ExpirableMixin)
    - `cache.py`: Search result caching in `search_cache` table (extends BaseModel + ExpirableMixin)
    - `genesys.py`: Genesys cache models - GenesysGroup, GenesysLocation, GenesysSkill (extends ServiceDataModel)
    - `session.py`: User session management with timeout tracking (extends BaseModel + ExpirableMixin)
    - `user_note.py`: Internal notes about users (extends BaseModel + TimestampMixin)
    - `employee_profiles.py`: **CONSOLIDATED** employee data including photos and Keystone info (replaces graph_photo.py and data_warehouse.py)
- **`app/services/`**: Service layer with base class hierarchy:
  - **Base Classes** (`base.py`):
    - `BaseConfigurableService`: Configuration management
    - `BaseAPIService`: HTTP request handling and error management
    - `BaseTokenService`: OAuth2 token management
    - `BaseSearchService`: User search functionality
    - `BaseCacheService`: Database caching patterns
    - `BaseAPITokenService`: Composite class for API services
  - **Services**:
    - `ldap_service.py`: Active Directory/LDAP integration with fuzzy search and timeout handling
    - `genesys_service.py`: Genesys Cloud API integration for contact center data
    - `graph_service.py`: Microsoft Graph API (beta) integration for enhanced Azure AD data
    - `refresh_employee_profiles.py`: **CONSOLIDATED** employee data service (replaces data_warehouse_service and graph photo handling)
    - `audit_service_postgres.py`: PostgreSQL-based audit logging for all system events
    - `configuration_service.py`: Simplified configuration access (wraps simple_config)
    - `simple_config.py`: Core configuration service with encryption support
    - `encryption_service.py`: Fernet-based encryption utilities
    - `genesys_cache_db.py`: PostgreSQL caching for Genesys groups, skills, locations
    - `token_refresh_service.py`: Background service for automatic API token renewal

### Frontend Architecture
WhoDis uses a hybrid server-side rendering approach that combines traditional Jinja2 templating with modern interactive elements:

#### **Tech Stack**
- **Jinja2 Templates**: Server-side templating for initial page structure and SEO-friendly content
- **HTMX**: Dynamic content updates and AJAX interactions without complex JavaScript frameworks
- **Tailwind CSS**: Utility-first CSS framework for responsive, modern styling
- **FontAwesome**: Icon library for visual hierarchy
- **Vanilla JavaScript**: Minimal client-side code for enhanced functionality

#### **Architecture Benefits**
- **Progressive Enhancement**: Works without JavaScript, enhanced with HTMX for better UX
- **Server-Side Rendering**: SEO-friendly, fast initial loads, no large JS bundles
- **Dynamic Updates**: HTMX enables SPA-like interactions without full page refreshes
- **Simple Debugging**: Server returns HTML fragments, not complex JSON APIs
- **Mobile-First Design**: Tailwind CSS provides responsive, touch-friendly interfaces

#### **File Structure**
- **`app/templates/`**: Jinja2 templates for page structure
  - `base.html`: Base template with Tailwind CSS and HTMX integration
  - `admin/`: Admin interface templates with modern card-based layouts
  - `search/`: Search interface with real-time result updates
- **`app/static/`**: Static assets
  - `js/`: Vanilla JavaScript with HTMX helpers and event handlers
  - `css/`: Minimal custom CSS alongside Tailwind utilities
  - `img/`: Application icons and branding assets

#### **Interaction Pattern**
1. **Initial Load**: Jinja2 renders complete HTML page with Tailwind styling
2. **Dynamic Updates**: HTMX makes requests that return HTML fragments
3. **Real-time Features**: Server-sent HTML updates via HTMX triggers
4. **Progressive Enhancement**: Core functionality works without JavaScript

### Database Architecture
- **PostgreSQL 12+** for all data persistence
- **Connection pooling** via SQLAlchemy
- **Encrypted storage** for sensitive configuration using Fernet
- **Automatic migrations** handled through SQL scripts
- **Thread-safe operations** with proper locking

### Authentication Flow
1. Primary authentication via Azure AD (`X-MS-CLIENT-PRINCIPAL-NAME` header)
2. Users are managed in PostgreSQL `users` table with roles
3. Role hierarchy: Admin > Editor > Viewer
4. Session management with configurable timeout and warning modal
5. All authentication events and access denials are logged to PostgreSQL
6. Snarky denial messages for unauthorized access attempts
7. Note: Basic authentication has been disabled for security reasons - only Azure AD SSO is supported

### Configuration Management
- **Minimal .env**: Only contains database connection and WHODIS_ENCRYPTION_KEY
- **Database storage**: All other configuration stored encrypted in PostgreSQL
- **Runtime updates**: Configuration can be changed without restart
- **Audit trail**: All configuration changes tracked in history table
- **Categories**: auth, flask, ldap, genesys, graph, search, session
- **Encryption**: Sensitive values encrypted with Fernet using PBKDF2-derived key

### Search Features
- **Concurrent Search**: Searches LDAP, Genesys, and Graph APIs simultaneously with configurable timeouts
- **Smart Matching**: Automatically matches users across services by email when single/multiple results exist
- **Fuzzy Search**: LDAP supports wildcard searches for partial matches
- **Multiple Results Handling**: Clean UI for selecting from multiple matches with detailed previews
- **Data Merging**: Combines LDAP and Graph data with Graph taking priority for enhanced fields
- **Result Caching**: Search results cached in PostgreSQL with expiration

### UI/UX Features
WhoDis features a modern, responsive interface built with Tailwind CSS and enhanced with HTMX for seamless interactions:

#### **Search Interface**
- **Two-Column Layout**: Azure AD (LDAP + Graph) and Genesys Cloud results side-by-side
- **Modern Search Bar**: Rounded pill-style search with shadow effects and real-time results
- **Status Indicators**: Visual badges for account status (Enabled/Disabled, Locked/Not Locked)
- **Phone Number Formatting**: Consistent +1 XXX-XXX-XXXX format with service tags
- **Date Formatting**: Clean M/D/YYYY format with 24-hour time and smart relative dates (e.g., "6Yr 8Mo ago")
- **Profile Photos**: Fetched from Microsoft Graph API with lazy loading and placeholder
- **Collapsible Groups**: AD and Genesys groups shown in expandable sections

#### **Admin Interface**
- **Modern Dashboard**: Card-based layout with real-time statistics and controls
- **Cache Management**: Interactive cards showing API token status with hover tooltips, cache statistics with refresh controls
- **User Management**: Clean table interface with role-based access controls
- **Configuration Editor**: Form-based config management with validation
- **Audit Log Viewer**: Searchable, filterable log interface with detail modals

#### **Mobile-First Design**
- **Responsive Grid**: Adaptive layouts (1 column mobile, 2 tablet, 3+ desktop)
- **Touch-Friendly**: Proper button sizing and spacing for mobile devices
- **Progressive Enhancement**: Core functionality works without JavaScript
- **Fast Loading**: Minimal JavaScript bundle, server-side rendering

#### **Visual Design**
- **Custom Branding**: TTCU colors (#007c59 for Azure AD, #FF4F1F for Genesys, #f2c655 for buttons)
- **Icon System**: FontAwesome icons for visual hierarchy and recognition
- **Color Coding**: Consistent status colors (green=good, yellow=warning, red=error)
- **Smooth Animations**: HTMX-powered transitions without complex JavaScript

#### **Interactive Features**
- **Session Timeout Warning**: Modal with countdown timer and extension option
- **Real-time Updates**: HTMX enables dynamic content updates without page refreshes
- **Hover Tooltips**: Contextual information on token expiration and status details
- **Confirmation Dialogs**: Prevent accidental destructive actions
- **User Notes**: Admin ability to add internal notes about users
- **Live Search**: Results update as you type with debounced requests

### API Integrations

#### LDAP Configuration
- Host, port, bind DN, and base DN stored encrypted in database
- Supports SSL/TLS connections
- Configurable timeouts for connection and operations
- Password expiration and last set date retrieval
- Credentials encrypted in configuration table

#### Genesys Cloud
- OAuth2 client credentials flow with automatic token refresh
- User search by name, email, or username
- Retrieves skills, queues, locations, groups, and contact information
- Tokens persisted in `api_tokens` table with automatic refresh
- Background caching of groups, skills, locations every 6 hours
- Credentials encrypted in configuration table

#### Microsoft Graph (Beta API)
- MSAL authentication with client credentials
- Enhanced user profile data including hire dates, password policies
- Binary photo retrieval with base64 encoding
- Fallback from user ID to UPN for photo fetching
- Tokens persisted and auto-refreshed
- Credentials encrypted in configuration table

### Background Services
- **Token Refresh Service**: Runs in background thread, checks tokens every 5 minutes
- **Genesys Cache Service**: Refreshes groups, skills, locations every 6 hours or on-demand
- **Session Cleanup**: Automatic removal of expired sessions on startup
- **Audit Log Cleanup**: Removes logs older than 90 days (configurable)
- **Session Monitoring**: Active monitoring of user sessions with inactivity tracking

### Token Management Architecture
WhoDis uses a unified token management system for consistent API access:

#### **Token Flow**
1. **Startup Validation**: All API services validate/refresh tokens during application startup
2. **Service Integration**: Cache initialization uses the same validated service instances
3. **Consistent Access**: All components use `service.get_access_token()` for token retrieval
4. **Database Persistence**: Tokens stored encrypted in `api_tokens` table with expiration tracking
5. **Background Refresh**: Automatic token renewal every 5 minutes via background service

#### **Cache Initialization**
- **Smart Startup**: Cache populates immediately if tokens are valid and cache needs refresh
- **On-Demand Fallback**: If startup token access fails, cache initializes when first accessed
- **Service Priority**: Uses validated service instances directly rather than database lookups
- **Efficient Logic**: Skips unnecessary refresh if cache is current (< 6 hours old)

### Session Management
- **Inactivity Timeout**: Configurable timeout (15min default) with 2min warning
- **Warning Modal**: Shows countdown timer before session expiration
- **Activity Tracking**: Mouse, keyboard, scroll, and touch events reset timer
- **Session Extension**: Users can extend their session from warning modal
- **SSO Integration**: Seamless re-authentication through Azure AD
- **JavaScript Client**: Handles client-side tracking and warning display

### Key Implementation Notes

#### **Backend Services**
- All services implement timeout handling to prevent hanging searches
- Graph API uses beta endpoints for additional fields
- Phone numbers from different sources are tagged (Genesys/Teams)
- Password fields prioritize LDAP data over Graph data
- Smart date calculations handle years, months, and days with abbreviations
- Memoryview/buffer objects from PostgreSQL BYTEA properly handled for encryption
- API token expiration includes timezone-aware handling for Central Daylight Time

#### **Frontend Architecture**
- **Hybrid Rendering**: Server-side Jinja2 templates enhanced with HTMX for dynamic updates
- **Progressive Enhancement**: Core functionality works without JavaScript, enhanced with HTMX
- **Mobile-First**: Tailwind CSS provides responsive design with touch-friendly interfaces
- **Performance**: Minimal JavaScript bundle (~10KB HTMX), fast server-side rendering
- **SEO-Friendly**: Complete HTML content served on initial load for search engine indexing
- **Debug-Friendly**: Server returns HTML fragments, making debugging straightforward

#### **UI/UX Patterns**
- **Card-Based Layouts**: Modern admin interface with interactive cache management cards
- **Real-Time Updates**: HTMX enables seamless content updates without page refreshes
- **Hover Tooltips**: Native browser tooltips show token expiration times and status details
- **Confirmation Dialogs**: JavaScript confirms prevent accidental destructive actions
- **Color-Coded Status**: Consistent visual indicators (green=good, yellow=warning, red=error)
- **Responsive Grids**: Adaptive layouts that stack on mobile, expand on desktop

### Audit Logging
- **Database**: PostgreSQL-based audit logging with comprehensive tracking
- **Event Types**:
  - `search`: All identity searches with query, results count, services used
  - `access`: Access denials with user, IP, and requested resource
  - `admin`: User management actions (add, update, delete users)
  - `config`: Configuration changes with before/after values
  - `error`: Application errors and exceptions with stack traces
- **Admin Panel**: View and search audit logs at `/admin/audit-logs`
- **Features**:
  - Dynamic filtering by date, user, search query, IP address
  - Real-time data loading with pagination
  - Detail view for each log entry
  - Color-coded event types
  - Export to CSV functionality
- **Performance**:
  - Indexed on timestamp, user_email, event_type, search_query, ip_address
  - Connection pooling for concurrent access
  - Automatic cleanup of old logs

### Security Considerations
- `SECRET_KEY` stored encrypted in database
- All API credentials encrypted at rest using Fernet with unique per-installation salt
- WHODIS_ENCRYPTION_KEY must be kept secure and backed up
- Unique salt file generated per installation (stored in project root for development, system directories for production)
- Graph client secrets with special characters handled properly
- All unauthorized access attempts are logged with full context
- No sensitive data logged in plaintext
- Database connections use connection pooling with SSL in production
- Failed login attempts tracked in `access_attempts` table
- CSRF protection via Flask sessions
- Session hijacking prevention with timeout and activity tracking
- Basic authentication disabled - only Azure AD SSO supported
- XSS protection through comprehensive input escaping with `escapeHtml()` function
- Content Security Policy (CSP) headers to prevent XSS attacks
- Security headers: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy
- Permissions Policy to disable unnecessary browser features

### Environment Variables (Minimal)
After migration, only these are needed in .env:
```
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=whodis_db
POSTGRES_USER=whodis_user
POSTGRES_PASSWORD=your-secure-password

# Encryption key for configuration
WHODIS_ENCRYPTION_KEY=your-generated-encryption-key
```

All other configuration is stored encrypted in the database and can be managed through the configuration service.

### Important Database Notes
- PostgreSQL credentials MUST remain in environment variables (bootstrap problem)
- Use `os.getenv()` for database connection, not `config_get()`
- Configuration service requires database connection to function
- Always handle memoryview objects from BYTEA columns properly
- Use thread-safe operations when accessing shared resources

### Development Tips
- Use `ruff` for linting (already configured)
- Use `mypy` for type checking (types-tabulate installed)
- Check configuration status before starting app
- Monitor audit logs for debugging
- Use background services for long-running operations
- Implement proper error handling with audit logging
- Test encryption/decryption after any configuration changes
- Run ANALYZE on new tables to prevent -1 row counts in admin UI
- Test session timeout behavior with different configurations
- See [Database Documentation](docs/database.md) for detailed troubleshooting