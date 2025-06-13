# 🕵️‍♂️ WhoDis - Enterprise Identity Search Platform

A comprehensive Flask-based identity lookup service that provides unified search across Active Directory, Microsoft Graph, and Genesys Cloud with plans for advanced reporting, compliance management, and workflow automation. Features consolidated employee profiles, encrypted configuration, comprehensive audit logging, and a modern hybrid UI architecture.

---

## 🚀 What's New in v2.0

**WhoDis 2.0** represents a major architectural overhaul with enterprise-grade features:

### Core Platform
- **🏗️ Consolidated Architecture**: Unified employee profiles replacing legacy models
- **🐘 PostgreSQL Backend**: Full migration from SQLite with performance optimizations
- **🔐 Encrypted Configuration**: Database-stored config with Fernet encryption
- **📊 Comprehensive Audit Logging**: Complete activity tracking and monitoring
- **🔄 Automatic Token Management**: Background service for API token refresh

### User Experience
- **📝 User Notes**: Internal admin notes for user documentation
- **🖼️ Photo Management**: Consolidated Microsoft Graph photo caching
- **🔧 Configuration Editor**: Web-based configuration management
- **⏱️ Session Management**: Smart timeout with inactivity warnings
- **🎨 Modern UI**: HTMX-powered dynamic updates with Tailwind CSS
- **📱 Phone Tooltips**: Detailed source information for phone numbers

### Security & Compliance
- **👥 Database User Management**: Persistent user storage with role-based access
- **📦 Enhanced Caching**: Consolidated employee data with Genesys integration
- **🚨 Security Monitoring**: Advanced access tracking and threat detection
- **🔒 Azure AD Only**: Streamlined authentication removing basic auth

---

## 🎯 Key Features

### Search Capabilities
* **Multi-Source Search**: Simultaneously searches LDAP, Microsoft Graph (Azure AD), and Genesys Cloud
* **Fuzzy Search**: LDAP supports wildcard searches for partial name/email matches
* **Concurrent Processing**: All three services searched simultaneously with timeout protection
* **Smart Result Matching**: Automatically matches users across systems by email
* **Multiple Result Handling**: Clean selection interface when multiple matches are found

### Data Integration
* **Azure AD Card**: Combines LDAP and Microsoft Graph data with Graph taking priority
* **Enhanced Fields**: Hire dates, birth dates, password policies, token refresh times
* **Profile Photos**: Fetches and caches user photos from Microsoft Graph API
* **Phone Number Tags**: Visual indicators showing source (Genesys/Teams)
* **User Notes**: Internal notes feature for admin documentation
* **Date Formatting**: Smart relative dates (e.g., "6Yr 8Mo ago") with consistent formatting

### Security & Compliance
* **Encrypted Storage**: All sensitive configuration values encrypted at rest with unique per-installation salt
* **Audit Trail**: Complete audit log of all searches, access attempts, and configuration changes
* **Role-Based Access**: Three-tier access control (Viewer, Editor, Admin)
* **Azure AD Only**: Basic authentication disabled for enhanced security
* **Session Management**: Persistent sessions with automatic cleanup and inactivity timeout
* **Inactivity Protection**: Configurable session timeout with warning modal (15min default)
* **Error Tracking**: Comprehensive error logging with stack traces
* **Configuration Management**: Web-based editor for runtime configuration changes

### UI/UX Features (Hybrid Architecture)
* **Progressive Enhancement**: Server-side Jinja2 templates enhanced with HTMX for dynamic updates
* **Mobile-First Design**: Tailwind CSS responsive layouts with touch-friendly interfaces
* **Real-Time Updates**: HTMX enables SPA-like interactions without page refreshes
* **Modern Search Interface**: Two-column layout with pill-shaped search bar and real-time results
* **Status Indicators**: Visual badges for account status with hover tooltips
* **Card-Based Layouts**: Modern admin interface with interactive cache management
* **Session Management**: Smart timeout with countdown warnings and activity tracking
* **Profile Photos**: Lazy loading with Microsoft Graph integration

---

## 🛠 Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | Flask 3.0.0 | Web framework with blueprint architecture |
| Database | PostgreSQL 12+ | Data persistence with encrypted configuration |
| Encryption | cryptography (Fernet) | Configuration encryption with unique salts |
| Authentication | Azure AD SSO | Single sign-on with role-based access control |
| LDAP | ldap3 | Active Directory integration with fuzzy search |
| Graph API | MSAL + requests | Microsoft Graph integration with enhanced profiles |
| Genesys | OAuth2 + requests | Contact center data with cached groups/skills |
| ORM | SQLAlchemy | Database abstraction with base model hierarchy |
| Frontend | **Hybrid Architecture** | **Server-side Jinja2 + HTMX for dynamic updates** |
| UI Framework | **Tailwind CSS** | **Utility-first responsive design** |
| Icons | **FontAwesome** | **Visual hierarchy and recognition** |
| Task Management | Background threads | Token refresh, cache updates, session cleanup |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Virtual environment tool (venv/virtualenv)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jslitzkerttcu/Who-Dis.git
   cd Who-Dis
   ```

2. **Set up virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up PostgreSQL database**:
   ```bash
   # Create database and user
   sudo -u postgres psql
   CREATE DATABASE whodis_db;
   CREATE USER whodis_user WITH PASSWORD 'your-secure-password';
   GRANT ALL PRIVILEGES ON DATABASE whodis_db TO whodis_user;
   \q
   
   # Run database schema
   psql -U whodis_user -d whodis_db -h localhost -f database/create_tables.sql
   
   # Run table statistics (prevents -1 row counts)
   psql -U postgres -d whodis_db -h localhost -f database/analyze_tables.sql
   ```

5. **Configure minimal environment**:
   ```bash
   # Create .env file with only database connection and encryption key
   cat > .env << EOF
   # PostgreSQL Configuration
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=whodis_db
   POSTGRES_USER=whodis_user
   POSTGRES_PASSWORD=your-secure-password
   
   # Encryption key for configuration
   WHODIS_ENCRYPTION_KEY=$(python -c "from app.services.encryption_service import EncryptionService; print(EncryptionService.generate_key())")
   EOF
   ```

6. **Migrate configuration to database**:
   ```bash
   # First, add all your API credentials to .env temporarily
   # Then run the migration script
   python scripts/migrate_config_to_db.py
   
   # Verify encryption is working
   python scripts/verify_encrypted_config.py
   
   # Remove sensitive values from .env after verification
   ```

7. **Run the application**:
   ```bash
   python run.py
   ```

   Access at [http://localhost:5000](http://localhost:5000)

---

## 📋 Configuration Management

### Encrypted Configuration System

WhoDis uses a sophisticated configuration management system where:
- **Database Storage**: All configuration stored in PostgreSQL
- **Encryption**: Sensitive values encrypted using Fernet symmetric encryption
- **Minimal .env**: Only database connection and encryption key in .env file
- **Runtime Updates**: Configuration can be changed without restarting
- **Audit Trail**: All configuration changes are logged

### 🔐 WHODIS_ENCRYPTION_KEY - Critical Information

The `WHODIS_ENCRYPTION_KEY` is the master key that encrypts all sensitive configuration values in the database.

**⚠️ WARNING: Changing this key will make ALL encrypted configuration unreadable!**

#### What happens when the key is changed:
- All encrypted values in the database become undecryptable
- The application will return empty strings for encrypted settings
- You'll need to re-enter all passwords and secrets

#### How to safely change the encryption key:

1. **Export current configuration** (create a backup):
   ```bash
   python scripts/export_config.py > config_backup.json
   ```

2. **Generate a new encryption key**:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

3. **Update the key in .env**:
   ```bash
   # Edit .env and replace WHODIS_ENCRYPTION_KEY with the new value
   ```

4. **Re-encrypt all values** with the new key:
   ```bash
   python scripts/reencrypt_config.py
   ```

5. **Restart the application**

#### Best Practices:
- **Backup the key** in a secure location (password manager, secrets vault)
- **Never commit** the .env file to version control
- **Use a strong key** in production (generate, don't create manually)
- **Document key rotation** in your operational procedures

### Configuration Categories

| Category | Purpose | Encrypted |
|----------|---------|-----------|
| auth | User access lists (viewers, editors, admins) | ✅ |
| flask | Application settings (host, port, debug, secret_key) | Partial |
| ldap | Active Directory settings and credentials | Partial |
| genesys | Genesys Cloud OAuth credentials | Partial |
| graph | Microsoft Graph API credentials | ✅ |
| search | Search timeout settings | ❌ |
| session | Session timeout settings (timeout, warning, check interval) | ❌ |

For detailed database setup and configuration management, see [Database Documentation](docs/database.md).

---

## 🗂 Project Structure

```
WhoDis/
├── app/                           # Application code
│   ├── __init__.py               # Flask app factory with config service
│   ├── blueprints/               # Route handlers
│   │   ├── admin/                # Admin panel with user & audit management
│   │   ├── home/                 # Landing page and login
│   │   ├── search/               # Search interface and logic
│   │   └── session/              # Session management endpoints
│   ├── database.py               # Database configuration
│   ├── middleware/               # Authentication and authorization
│   │   └── auth.py               # RBAC with database/config fallback
│   ├── models/                   # SQLAlchemy models
│   │   ├── access.py             # Access attempt tracking
│   │   ├── audit.py              # Audit log model
│   │   ├── cache.py              # Search cache model
│   │   ├── configuration.py      # Configuration model
│   │   ├── error.py              # Error log model
│   │   ├── genesys.py            # Genesys cache models
│   │   ├── employee_profiles.py  # Consolidated employee data with photos
│   │   ├── session.py            # User session model with timeout support
│   │   ├── user.py               # User management model
│   │   └── user_note.py          # User notes model
│   ├── services/                 # External service integrations
│   │   ├── audit_service_postgres.py    # PostgreSQL audit logging
│   │   ├── configuration_service.py     # Encrypted config management
│   │   ├── encryption_service.py        # Fernet encryption utilities
│   │   ├── genesys_cache_db.py         # Genesys data caching
│   │   ├── genesys_service.py          # Genesys Cloud API
│   │   ├── graph_service.py            # Microsoft Graph API
│   │   ├── ldap_service.py             # Active Directory queries
│   │   └── token_refresh_service.py    # Background token management
│   ├── static/                   # CSS, JS, images
│   │   ├── css/                  # Stylesheets
│   │   ├── img/                  # Images and icons
│   │   └── js/                   # JavaScript files
│   └── templates/                # Jinja2 HTML templates
│       ├── admin/                # Admin panel templates
│       ├── home/                 # Home and login pages
│       └── search/               # Search interface
├── database/                     # Database SQL scripts
│   ├── create_database.sql       # Database and user creation
│   ├── create_tables.sql         # Complete schema (all tables, triggers, etc.)
│   └── analyze_tables.sql        # Table statistics update
├── docs/                         # Documentation
│   └── database.md               # Database documentation
├── logs/                         # Application logs (git-ignored)
├── scripts/                      # Utility scripts
│   ├── migrate_config_to_db.py  # Migrate .env to encrypted database
│   ├── verify_encrypted_config.py # Verify encryption setup
│   ├── check_config_status.py   # Quick configuration check
│   └── reencrypt_config.py      # Re-encrypt all sensitive values
├── requirements.txt              # Python dependencies
├── run.py                        # Application entry point
├── .env                          # Minimal environment (DB + encryption key only)
├── CLAUDE.md                     # AI assistant guidelines
└── README.md                     # This file
```

---

## 🔐 Authentication & Authorization

### Authentication Method
**Azure AD SSO**: Checks `X-MS-CLIENT-PRINCIPAL-NAME` header from Azure App Service

*Note: Basic authentication has been removed for enhanced security.*

### Role Hierarchy
- **👀 Viewers**: Can search and view user information
- **✏️ Editors**: Can search, view, and modify user data
- **👑 Admins**: Full access including user management and audit logs

### Access Control
- Users managed in database with fallback to encrypted configuration
- Failed access attempts logged with IP, user agent, and timestamp
- Unauthorized users see creative denial messages
- Session management with automatic expiration and timeout warnings
- Dedicated login page at `/login` with SSO support

---

## 🔍 Advanced Features

### Audit Logging
- **Search Auditing**: Every search logged with query, results count, and services used
- **Access Tracking**: Failed login attempts with denial reasons
- **Admin Actions**: User management changes tracked
- **Error Logging**: Application errors with stack traces
- **Configuration Changes**: All config modifications logged
- **Session Events**: Login, logout, and timeout events

### Background Services
- **Token Refresh**: Automatic renewal of API tokens before expiration
- **Cache Management**: Genesys data refreshed every 6 hours
- **Session Cleanup**: Expired sessions removed automatically
- **Database Maintenance**: Old audit logs cleaned up periodically
- **Photo Caching**: Consolidated photo storage in employee profiles

### Performance Optimizations
- **Connection Pooling**: SQLAlchemy connection pool for PostgreSQL
- **Result Caching**: Search results cached with expiration
- **Concurrent Searches**: ThreadPoolExecutor for parallel API calls
- **Lazy Loading**: Profile photos loaded on-demand
- **Indexed Queries**: Database indexes on frequently searched fields

---

## 🎨 UI Features

### Modern Design
- **Responsive Layout**: Works on desktop and tablet devices
- **Dark Mode Ready**: CSS variables for easy theming
- **Status Indicators**: Visual badges for account status
- **Loading States**: Skeleton screens during searches
- **Error Handling**: User-friendly error messages

### Admin Dashboard
- **User Management**: Add, edit, deactivate users with notes
- **Configuration Editor**: Modify settings without restart
- **Audit Log Viewer**: Search and filter audit logs
- **Session Monitor**: View active sessions and timeout status
- **Real-time Updates**: Live data refresh without page reload
- **Export Options**: Download audit logs as CSV

---

## 📊 API Integrations

### LDAP/Active Directory
- Searches by username, email, display name
- Password expiration from computed attributes
- Group membership enumeration
- Account lockout status
- Fuzzy matching with wildcards

### Microsoft Graph (Beta API)
- Enhanced user profiles with extended properties
- Binary photo retrieval with database caching
- Manager relationships with expansion
- License assignments and usage location
- Token refresh and session validity
- Lazy loading of photos for performance

### Genesys Cloud
- OAuth2 client credentials flow
- User skills, queues, and locations
- Multiple phone number types
- Group membership with caching
- Automatic token refresh

---

## 🚨 Security Best Practices

1. **Environment Security**
   - Use strong PostgreSQL password
   - Generate unique WHODIS_ENCRYPTION_KEY
   - Never commit .env file

2. **Database Security**
   - Regular backups of PostgreSQL
   - Use SSL for database connections in production
   - Implement database user permissions properly

3. **Application Security**
   - Run behind HTTPS reverse proxy
   - Implement rate limiting
   - Regular security updates
   - Monitor audit logs for suspicious activity

4. **API Security**
   - Rotate API credentials regularly
   - Use service accounts with minimal permissions
   - Monitor API usage and quotas

---

## 🐛 Troubleshooting

### Database Issues
```bash
# Check configuration status
python scripts/check_config_status.py

# Verify encrypted values
python scripts/verify_encrypted_config.py

# Re-encrypt all values if needed
python scripts/reencrypt_config.py
```

### Common Problems

**"Error decrypting configuration"**
- Check WHODIS_ENCRYPTION_KEY in .env
- Run verification script
- Re-encrypt values if key changed

**"Database connection failed"**
- Verify PostgreSQL is running
- Check credentials in .env
- Ensure database exists

**"No search results"**
- Check service credentials in configuration
- Verify API permissions
- Review audit logs for errors

For detailed troubleshooting, see [Database Documentation](docs/database.md).

---

## 📈 Monitoring & Maintenance

### Health Checks
- Token expiration monitoring
- Database connection pooling stats
- API rate limit tracking
- Cache hit/miss ratios

### Regular Maintenance
```sql
-- Clean up old data (90 days audit, 30 days errors)
SELECT cleanup_old_data();

-- Check table sizes
SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename::regclass))
FROM pg_tables WHERE schemaname = 'public';

-- Active sessions
SELECT * FROM user_sessions WHERE expires_at > NOW();
```

---

## 🧑‍💻 Development

### Code Quality
```bash
# Run linting
ruff check --fix

# Type checking
mypy app/ scripts/

# Format code
black .
```

### Testing
```bash
# Run tests (when implemented)
pytest

# Coverage report
pytest --cov=app
```

---

## 📝 Roadmap

- [x] PostgreSQL migration
- [x] Encrypted configuration
- [x] Comprehensive audit logging
- [x] Background token refresh
- [x] Genesys data caching
- [x] User notes feature
- [x] Configuration web editor
- [x] Photo caching
### Strategic Roadmap (High Priority - Next Phase)

#### Phase 1: Enhanced Data Integration
- [ ] **Expanded Profile Cards**: Leverage all available data fields from Azure AD, Graph APIs, and Genesys
  - Department, cost center, employee ID, hire date, manager chain
  - Sign-in activity, licenses, group memberships, device registrations
  - Historical metrics, schedule adherence, skill proficiency, call logs
- [ ] **Cross-System Correlation**: Improve data matching and conflict resolution
- [ ] **Advanced Search & Export**: Multi-field search, filtering, CSV/Excel export

#### Phase 2: Comprehensive Reporting Suite  
- [ ] **Azure AD Reports**: License utilization, user activity, security posture, MFA adoption
- [ ] **Security & Compliance**: Risk assessment, guest user management, secure score monitoring
- [ ] **Communication Analytics**: Exchange mailbox stats, Teams usage, email security metrics
- [ ] **Scheduled Reports**: Admin tools for automated report generation and alerting

#### Phase 3: Job Role Compliance Matrix (Critical for Audit)
- [ ] **Role Mapping**: Map job codes/titles to expected system roles across all platforms
- [ ] **Compliance Checking**: Automated detection of missing or extra privileges
- [ ] **Audit Dashboard**: Visual compliance matrix with actionable insights
- [ ] **Data Warehouse Integration**: Pull actual roles from warehouse with sync capabilities

#### Future Enhancements
- [ ] Advanced user management and workflow automation
- [ ] REST API endpoints for external ITSM/HR system integrations
- [ ] AI-powered analytics and predictive insights
- [ ] Self-service portal with approval workflows

---

## ⚖️ License

[Insert your license here]

---

## 🙏 Acknowledgments

Built with ❤️ by the TTCU Development Team

Special thanks to all contributors who helped evolve WhoDis from a simple LDAP tool to a comprehensive enterprise identity platform.

---

*For detailed technical documentation, see the [docs](docs/) folder.*
*For AI assistant guidelines, see [CLAUDE.md](CLAUDE.md)*