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

# Run the application
python run.py
```

The application runs on http://localhost:5000 with debug mode enabled.

### Testing
No test framework is currently configured. When implementing tests, consider adding pytest to requirements.txt.

### Linting
No linter is currently configured. Consider adding flake8 or pylint to the project.

## Architecture

### Application Structure
WhoDis is a Flask-based identity lookup service with integrated search across multiple identity providers:

- **`app/__init__.py`**: Application factory that initializes Flask, loads environment config, and registers blueprints
- **`app/blueprints/`**: Contains three main blueprints:
  - `home`: Landing page with product branding (requires authentication)
  - `search`: Identity search interface with real-time results (requires 'viewer' role minimum)
  - `admin`: Admin panel with user management (requires 'admin' role)
- **`app/middleware/auth.py`**: Implements role-based authentication with Azure AD integration and fallback to basic auth
- **`app/services/`**: Contains service integrations:
  - `ldap_service.py`: Active Directory/LDAP integration with fuzzy search and timeout handling
  - `genesys_service.py`: Genesys Cloud API integration for contact center data
  - `graph_service.py`: Microsoft Graph API (beta) integration for enhanced Azure AD data and photos
  - `genesys_cache.py`: Token caching for Genesys API authentication
  - `audit_service.py`: SQLite-based audit logging for searches, access, and admin actions

### Authentication Flow
1. Primary authentication via Azure AD (`X-MS-CLIENT-PRINCIPAL-NAME` header)
2. Fallback to HTTP basic authentication
3. Users are whitelisted in `.env` file under VIEWERS, EDITORS, and ADMINS
4. Role hierarchy: Admin > Editor > Viewer
5. All authentication events and access denials are logged to SQLite audit database (`logs/audit.db`)

### Search Features
- **Concurrent Search**: Searches LDAP, Genesys, and Graph APIs simultaneously with configurable timeouts
- **Smart Matching**: Automatically matches users across services by email when single/multiple results exist
- **Fuzzy Search**: LDAP supports wildcard searches for partial matches
- **Multiple Results Handling**: Clean UI for selecting from multiple matches with detailed previews
- **Data Merging**: Combines LDAP and Graph data with Graph taking priority for enhanced fields

### UI/UX Features
- **Two-Column Layout**: Azure AD (LDAP + Graph) and Genesys Cloud results side-by-side
- **Modern Search Bar**: Rounded pill-style search with shadow effects
- **Status Indicators**: Visual badges for account status (Enabled/Disabled, Locked/Not Locked)
- **Phone Number Formatting**: Consistent +1 XXX-XXX-XXXX format with service tags
- **Date Formatting**: Clean M/D/YYYY format with 24-hour time and smart relative dates (e.g., "6Yr 8Mo ago")
- **Profile Photos**: Fetched from Microsoft Graph API with binary data handling
- **Collapsible Groups**: AD and Genesys groups shown in expandable sections
- **Custom Branding**: TTCU colors (#007c59 for Azure AD, #FF4F1F for Genesys, #f2c655 for buttons)

### API Integrations

#### LDAP Configuration
- Host, port, bind DN, and base DN configured via environment variables
- Supports SSL/TLS connections
- Configurable timeouts for connection and operations
- Password expiration and last set date retrieval

#### Genesys Cloud
- OAuth2 client credentials flow with automatic token refresh
- User search by name, email, or username
- Retrieves skills, queues, locations, groups, and contact information
- Caches authentication tokens to reduce API calls

#### Microsoft Graph (Beta API)
- MSAL authentication with client credentials
- Enhanced user profile data including hire dates, password policies
- Binary photo retrieval with base64 encoding
- Fallback from user ID to UPN for photo fetching

### Key Implementation Notes
- All services implement timeout handling to prevent hanging searches
- Graph API uses beta endpoints for additional fields
- Phone numbers from different sources are tagged (Genesys/Teams)
- Password fields prioritize LDAP data over Graph data
- Smart date calculations handle years, months, and days with abbreviations
- Custom CSS for modern rounded search bar and consistent button styling

### Audit Logging
- **Database**: SQLite-based audit log stored at `logs/audit.db`
- **Event Types**:
  - `search`: All identity searches with query, results count, services used
  - `access`: Access denials with user, IP, and requested resource
  - `admin`: User management actions (add, update, delete users)
  - `config`: Configuration changes (.env file updates)
  - `error`: Application errors and exceptions
- **Admin Panel**: View and search audit logs at `/admin/audit-logs`
- **Features**:
  - Dynamic filtering by date, user, search query, IP address
  - Real-time data loading with pagination
  - Detail view for each log entry
  - Color-coded event types
- **Database Configuration**:
  - Uses Flask-aware SQLite integration with per-request connections
  - WAL mode enabled for better concurrent access
  - Automatic retry on database lock errors
  - Indexed fields for fast queries: timestamp, user_email, event_type, search_query

### Security Considerations
- Change `SECRET_KEY` in `.env` before production deployment
- All API credentials stored in environment variables
- Graph client secrets with special characters must be quoted in `.env`
- All unauthorized access attempts are logged with timestamp, user, IP, and requested path
- No sensitive data logged in debug mode

### Environment Variables Required
```
# Flask Configuration
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=True
SECRET_KEY=your-secret-key

# User Access Control
VIEWERS=viewer1@example.com,viewer2@example.com
EDITORS=editor@example.com
ADMINS=admin@example.com

# LDAP Configuration
LDAP_HOST=ldap://your-dc.example.com
LDAP_PORT=389
LDAP_USE_SSL=False
LDAP_BIND_DN=CN=service,OU=Accounts,DC=example,DC=com
LDAP_BIND_PASSWORD=your-password
LDAP_BASE_DN=DC=example,DC=com
LDAP_USER_SEARCH_BASE=OU=Employees,DC=example,DC=com
LDAP_CONNECT_TIMEOUT=5
LDAP_OPERATION_TIMEOUT=10

# Genesys Configuration
GENESYS_CLIENT_ID=your-client-id
GENESYS_CLIENT_SECRET=your-secret
GENESYS_REGION=mypurecloud.com
GENESYS_API_TIMEOUT=15

# Microsoft Graph Configuration
GRAPH_CLIENT_ID=your-client-id
GRAPH_CLIENT_SECRET="your-secret-with-special-chars"
GRAPH_TENANT_ID=your-tenant-id
GRAPH_API_TIMEOUT=15

# Search Configuration
SEARCH_OVERALL_TIMEOUT=20
```