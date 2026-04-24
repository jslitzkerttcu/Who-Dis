# Technology Stack

**Analysis Date:** 2026-04-24

## Languages

**Primary:**
- Python 3.8+ - Backend application, services, and scripts

**Secondary:**
- Jinja2 - Server-side templating for HTML
- HTML5 - Frontend markup with HTMX enhancement
- CSS3 - Styling via Tailwind CSS utility classes
- JavaScript - Minimal client-side interactivity and HTMX integration

## Runtime

**Environment:**
- Python 3.8+ (interpreter and standard library)

**Package Manager:**
- pip with venv (standard Python virtual environments)
- Lockfile: None (uses requirements.txt pinned versions)

## Frameworks

**Core:**
- Flask 3.1.3 - Web framework with blueprint-based architecture
- Flask-SQLAlchemy 3.1.1 - ORM integration for database models
- Flask-WTF 1.2.2 - CSRF protection via double-submit cookie pattern
- SQLAlchemy 2.0.45 - Object-relational mapping and query builder

**Authentication & Security:**
- cryptography 46.0.7 - Fernet encryption for configuration values
- msal 1.34.0 - Microsoft Authentication Library for Graph API

**API Clients:**
- ldap3 2.9.1 - LDAP/Active Directory client
- requests 2.33.0 - HTTP client for REST APIs
- httpx 0.28.1 - Alternative async HTTP client (included but requests primary)

**Database:**
- psycopg2-binary 2.9.11 - PostgreSQL adapter for Python

**Utilities:**
- python-dotenv 1.2.2 - Environment variable loading from .env
- psutil - System utilities and resource monitoring
- pyodbc 5.3.0 - ODBC database driver (legacy support)
- pytz 2025.2 - Timezone handling and conversions
- tabulate 0.9.0 - Formatted table output for CLI tools

**Development & Quality:**
- ruff - Fast Python linter and code formatter
- mypy - Static type checking for Python
- types-* packages - Type stubs for dependencies (tabulate, flask, requests, psycopg2, pytz, cryptography)

**Frontend:**
- Tailwind CSS - Utility-first CSS framework (referenced in templates)
- FontAwesome - Icon library (referenced in templates)
- HTMX - Client-side HTML interactivity (referenced in templates)

## Key Dependencies

**Critical:**
- Flask 3.1.3 - Web framework, routing, request handling
- SQLAlchemy 2.0.45 - Data persistence abstraction layer
- psycopg2-binary 2.9.11 - PostgreSQL connectivity (required for production)

**Infrastructure:**
- ldap3 2.9.1 - Active Directory/LDAP integration for employee search
- msal 1.34.0 - OAuth2 token acquisition for Microsoft Graph API
- requests 2.33.0 - HTTP client for Genesys Cloud and Graph APIs
- cryptography 46.0.7 - Fernet encryption for stored configuration

**Quality Assurance:**
- ruff - Code linting and style enforcement
- mypy - Type checking (enables `--strict` mode per CLAUDE.md)

## Configuration

**Environment:**
- .env file (required, not committed) with:
  - POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
  - WHODIS_ENCRYPTION_KEY (Fernet key for configuration encryption)
- Database-stored encrypted configuration via Configuration model (`app/models/configuration.py`)
- Configuration accessed via `config_get()` functions (automatic decryption)

**Build:**
- No build step required (pure Python Flask application)
- Dependency installation: `pip install -r requirements.txt`
- Database initialization: SQL files in `database/` directory
- Virtual environment: Standard Python venv

## Platform Requirements

**Development:**
- Python 3.8+
- PostgreSQL 12+ (required, SQLite fallback available but not recommended)
- Virtual environment (venv)

**Production:**
- Python 3.8+ runtime
- PostgreSQL 12+ database
- Web server: Gunicorn, uWSGI, or Azure App Service
- Reverse proxy: Nginx or Azure App Service (SSL/TLS termination)

## Port Configuration

**Default:**
- Flask development: 5000 (configurable via database configuration)
- PostgreSQL: 5432 (default)

## Encryption

**Configuration Encryption:**
- Algorithm: Fernet (symmetric encryption via `cryptography` library)
- Key: WHODIS_ENCRYPTION_KEY (base64-encoded 32-byte key)
- Per-installation salt: `.whodis_salt` file
- Sensitive values encrypted at rest in PostgreSQL configuration table

---

*Stack analysis: 2026-04-24*
