# 🕵️‍♂️ WhoDis - Enterprise Identity Search Platform

A comprehensive Flask-based identity lookup service that searches across Active Directory, Microsoft Graph, and Genesys Cloud. Features PostgreSQL database backend, encrypted configuration management, comprehensive audit logging, and a modern UI with role-based access control.

---

## 🚀 What's New in v2.0

**WhoDis** has undergone a major upgrade with enterprise-grade features:

- **🐘 PostgreSQL Backend**: Migrated from SQLite to PostgreSQL for better performance and scalability
- **🔐 Encrypted Configuration**: Sensitive credentials are now encrypted in the database using Fernet encryption
- **📊 Comprehensive Audit Logging**: All searches, access attempts, and admin actions are logged to PostgreSQL
- **👥 Database User Management**: Admin panel for managing users with persistent storage
- **🔄 Automatic Token Management**: API tokens are persisted and automatically refreshed in the background
- **📦 Genesys Data Caching**: Groups, skills, and locations are cached in PostgreSQL for faster searches
- **🚨 Enhanced Security**: Failed access attempts tracked, configuration changes audited, and error logging

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
* **Profile Photos**: Fetches user photos from Microsoft Graph API
* **Phone Number Tags**: Visual indicators showing source (Genesys/Teams)
* **Date Formatting**: Smart relative dates (e.g., "6Yr 8Mo ago") with consistent formatting

### Security & Compliance
* **Encrypted Storage**: All sensitive configuration values encrypted at rest
* **Audit Trail**: Complete audit log of all searches, access attempts, and configuration changes
* **Role-Based Access**: Three-tier access control (Viewer, Editor, Admin)
* **Session Management**: Persistent sessions with automatic cleanup
* **Error Tracking**: Comprehensive error logging with stack traces

### UI/UX Features
* **Status Badges**: Visual indicators for Enabled/Disabled and Locked/Not Locked accounts
* **Collapsible Groups**: AD and Genesys groups in expandable sections
* **Profile Photos**: Centered display with status badges
* **Modern Search Bar**: Pill-shaped design with subtle shadow effects
* **Admin Dashboard**: User management and audit log viewer

---

## 🛠 Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | Flask 3.0.0 | Web framework |
| Database | PostgreSQL 12+ | Data persistence |
| Encryption | cryptography (Fernet) | Configuration encryption |
| Authentication | Azure AD / Basic Auth | User authentication |
| LDAP | ldap3 | Active Directory integration |
| Graph API | MSAL + requests | Microsoft Graph integration |
| Genesys | OAuth2 + requests | Contact center data |
| ORM | SQLAlchemy | Database abstraction |
| Frontend | Bootstrap 5.3.0 | UI components |
| Task Management | Background threads | Token refresh service |

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
   CONFIG_ENCRYPTION_KEY=$(python -c "from app.services.encryption_service import EncryptionService; print(EncryptionService.generate_key())")
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

### Configuration Categories

| Category | Purpose | Encrypted |
|----------|---------|-----------|
| auth | User access lists (viewers, editors, admins) | ✅ |
| flask | Application settings (host, port, debug, secret_key) | Partial |
| ldap | Active Directory settings and credentials | Partial |
| genesys | Genesys Cloud OAuth credentials | Partial |
| graph | Microsoft Graph API credentials | ✅ |
| search | Search timeout settings | ❌ |

For detailed database setup and configuration management, see [Database Documentation](docs/database.md).

---

## 🗂 Project Structure

```
WhoDis/
├── app/                           # Application code
│   ├── __init__.py               # Flask app factory with config service
│   ├── blueprints/               # Route handlers
│   │   ├── admin/                # Admin panel with user & audit management
│   │   ├── home/                 # Landing page
│   │   └── search/               # Search interface and logic
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
│   │   ├── session.py            # User session model
│   │   └── user.py               # User management model
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
│   └── templates/                # Jinja2 HTML templates
├── database/                     # Database SQL scripts
│   ├── create_database.sql       # Database creation
│   ├── create_tables.sql         # Complete schema with encryption
│   └── add_*.sql                 # Migration scripts
├── docs/                         # Documentation
│   └── database.md               # Database documentation
├── logs/                         # Application logs (deprecated)
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

### Authentication Methods
1. **Azure AD (Primary)**: Checks `X-MS-CLIENT-PRINCIPAL-NAME` header from Azure App Service
2. **Basic Auth (Fallback)**: Username/password for development or non-Azure environments

### Role Hierarchy
- **👀 Viewers**: Can search and view user information
- **✏️ Editors**: Can search, view, and modify user data
- **👑 Admins**: Full access including user management and audit logs

### Access Control
- Users managed in database with fallback to encrypted configuration
- Failed access attempts logged with IP, user agent, and timestamp
- Unauthorized users see creative denial messages
- Session management with automatic expiration

---

## 🔍 Advanced Features

### Audit Logging
- **Search Auditing**: Every search logged with query, results count, and services used
- **Access Tracking**: Failed login attempts with denial reasons
- **Admin Actions**: User management changes tracked
- **Error Logging**: Application errors with stack traces
- **Configuration Changes**: All config modifications logged

### Background Services
- **Token Refresh**: Automatic renewal of API tokens before expiration
- **Cache Management**: Genesys data refreshed every 6 hours
- **Session Cleanup**: Expired sessions removed automatically
- **Database Maintenance**: Old audit logs cleaned up periodically

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
- **User Management**: Add, edit, deactivate users
- **Audit Log Viewer**: Search and filter audit logs
- **Real-time Updates**: Live data refresh without page reload
- **Bulk Operations**: Manage multiple users at once
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
- Binary photo retrieval and caching
- Manager relationships with expansion
- License assignments and usage location
- Token refresh and session validity

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
   - Generate unique CONFIG_ENCRYPTION_KEY
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
- Check CONFIG_ENCRYPTION_KEY in .env
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
- [ ] Redis caching layer
- [ ] REST API endpoints
- [ ] Bulk user operations
- [ ] Advanced search filters
- [ ] Mobile responsive design
- [ ] Dark mode theme
- [ ] SAML authentication
- [ ] Export functionality

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