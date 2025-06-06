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

# Configure encryption and migrate settings
python scripts/migrate_config_to_db.py
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

### Database Management
```bash
# Check configuration status
python scripts/check_config_status.py

# Verify encrypted configuration
python scripts/verify_encrypted_config.py

# Re-encrypt all sensitive values
python scripts/reencrypt_config.py

# Fix encryption issues
python scripts/fix_encrypted_values.py

# Diagnose configuration problems
python scripts/diagnose_config.py
```

## Architecture

### Application Structure
WhoDis is a Flask-based identity lookup service with PostgreSQL backend and integrated search across multiple identity providers:

- **`app/__init__.py`**: Application factory that initializes Flask, database, configuration service, and registers blueprints
- **`app/database.py`**: Database configuration and connection management
- **`app/blueprints/`**: Contains three main blueprints:
  - `home`: Landing page with product branding (requires authentication)
  - `search`: Identity search interface with real-time results (requires 'viewer' role minimum)
  - `admin`: Admin panel with user management and audit logs (requires 'admin' role)
- **`app/middleware/auth.py`**: Implements role-based authentication with database users, encrypted config fallback, and basic auth
- **`app/models/`**: SQLAlchemy models for all database tables:
  - `user.py`: User management with roles
  - `configuration.py`: Encrypted configuration storage
  - `audit.py`: Audit log entries
  - `access.py`: Access attempt tracking
  - `error.py`: Error logging
  - `genesys.py`: Genesys cache models
  - `session.py`: User session management
  - `cache.py`: Search result caching
- **`app/services/`**: Contains service integrations:
  - `ldap_service.py`: Active Directory/LDAP integration with fuzzy search and timeout handling
  - `genesys_service.py`: Genesys Cloud API integration for contact center data
  - `graph_service.py`: Microsoft Graph API (beta) integration for enhanced Azure AD data and photos
  - `audit_service_postgres.py`: PostgreSQL-based audit logging for all system events
  - `configuration_service.py`: Encrypted configuration management with caching
  - `encryption_service.py`: Fernet-based encryption utilities
  - `genesys_cache_db.py`: PostgreSQL caching for Genesys groups, skills, locations
  - `token_refresh_service.py`: Background service for automatic API token renewal

### Database Architecture
- **PostgreSQL 12+** for all data persistence
- **Connection pooling** via SQLAlchemy
- **Encrypted storage** for sensitive configuration using Fernet
- **Automatic migrations** handled through SQL scripts
- **Thread-safe operations** with proper locking

### Authentication Flow
1. Primary authentication via Azure AD (`X-MS-CLIENT-PRINCIPAL-NAME` header)
2. Fallback to HTTP basic authentication
3. Users are managed in PostgreSQL `users` table
4. Secondary fallback to encrypted configuration in database
5. Final fallback to environment variables (migration path)
6. Role hierarchy: Admin > Editor > Viewer
7. All authentication events and access denials are logged to PostgreSQL

### Configuration Management
- **Minimal .env**: Only contains database connection and CONFIG_ENCRYPTION_KEY
- **Database storage**: All other configuration stored encrypted in PostgreSQL
- **Runtime updates**: Configuration can be changed without restart
- **Audit trail**: All configuration changes tracked in history table
- **Categories**: auth, flask, ldap, genesys, graph, search
- **Encryption**: Sensitive values encrypted with Fernet using PBKDF2-derived key

### Search Features
- **Concurrent Search**: Searches LDAP, Genesys, and Graph APIs simultaneously with configurable timeouts
- **Smart Matching**: Automatically matches users across services by email when single/multiple results exist
- **Fuzzy Search**: LDAP supports wildcard searches for partial matches
- **Multiple Results Handling**: Clean UI for selecting from multiple matches with detailed previews
- **Data Merging**: Combines LDAP and Graph data with Graph taking priority for enhanced fields
- **Result Caching**: Search results cached in PostgreSQL with expiration

### UI/UX Features
- **Two-Column Layout**: Azure AD (LDAP + Graph) and Genesys Cloud results side-by-side
- **Modern Search Bar**: Rounded pill-style search with shadow effects
- **Status Indicators**: Visual badges for account status (Enabled/Disabled, Locked/Not Locked)
- **Phone Number Formatting**: Consistent +1 XXX-XXX-XXXX format with service tags
- **Date Formatting**: Clean M/D/YYYY format with 24-hour time and smart relative dates (e.g., "6Yr 8Mo ago")
- **Profile Photos**: Fetched from Microsoft Graph API with binary data handling
- **Collapsible Groups**: AD and Genesys groups shown in expandable sections
- **Custom Branding**: TTCU colors (#007c59 for Azure AD, #FF4F1F for Genesys, #f2c655 for buttons)
- **Admin Dashboard**: User management and audit log viewer with filtering

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
- **Genesys Cache Service**: Refreshes groups, skills, locations every 6 hours
- **Session Cleanup**: Automatic removal of expired sessions
- **Audit Log Cleanup**: Removes logs older than 90 days (configurable)

### Key Implementation Notes
- All services implement timeout handling to prevent hanging searches
- Graph API uses beta endpoints for additional fields
- Phone numbers from different sources are tagged (Genesys/Teams)
- Password fields prioritize LDAP data over Graph data
- Smart date calculations handle years, months, and days with abbreviations
- Custom CSS for modern rounded search bar and consistent button styling
- Memoryview/buffer objects from PostgreSQL BYTEA properly handled for encryption

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
- All API credentials encrypted at rest using Fernet
- CONFIG_ENCRYPTION_KEY must be kept secure and backed up
- Graph client secrets with special characters handled properly
- All unauthorized access attempts are logged with full context
- No sensitive data logged in plaintext
- Database connections use connection pooling with SSL in production
- Failed login attempts tracked in `access_attempts` table

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
CONFIG_ENCRYPTION_KEY=your-generated-encryption-key
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