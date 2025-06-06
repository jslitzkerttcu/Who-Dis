# WhoDis Database Documentation

## Table of Contents
- [Initial Setup](#initial-setup)
- [Table Descriptions](#table-descriptions)
- [Configuration Management](#configuration-management)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)
- [Performance Tuning](#performance-tuning)

## Initial Setup

### Prerequisites
- PostgreSQL 12+ installed and running
- psql command-line tool or pgAdmin

### 1. Create Database and User

Connect to PostgreSQL as a superuser:

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Or if using psql with credentials
psql -U postgres
```

Then run the following SQL commands:

```sql
-- Create database
CREATE DATABASE whodis_db;

-- Create user
CREATE USER whodis_user WITH PASSWORD 'your_secure_password_here';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE whodis_db TO whodis_user;

-- Exit
\q
```

### 2. Create Tables

Run the schema file to create all tables:

```bash
# From the WhoDis directory
psql -U whodis_user -d whodis_db -h localhost -f database/create_tables.sql

# Or if you need to specify port
psql -h localhost -p 5432 -U whodis_user -d whodis_db -f database/create_tables.sql
```

### 3. Configure Environment Variables

After setting up encrypted configuration, your `.env` file will only need:

```env
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=whodis_db
POSTGRES_USER=whodis_user
POSTGRES_PASSWORD=your_secure_password_here

# Encryption key for configuration
CONFIG_ENCRYPTION_KEY=your_encryption_key_here
```

To generate an encryption key:
```bash
python -c "from app.services.encryption_service import EncryptionService; print(EncryptionService.generate_key())"
```

### 4. Verify Installation

Check that all tables were created:

```sql
-- List all tables
\dt

-- Should show:
-- api_tokens, users, configuration, audit_log, error_log, 
-- access_attempts, genesys_groups, genesys_locations, 
-- genesys_skills, search_cache, user_sessions
```

## Table Descriptions

### Core Tables
- **api_tokens**: Stores API tokens for Genesys and Microsoft Graph services with automatic expiration tracking
- **users**: User authentication and authorization with role-based access (viewer, editor, admin)
- **configuration**: Database-stored configuration values with encryption support for sensitive data
- **configuration_history**: Audit trail of all configuration changes

### Audit & Logging Tables
- **audit_log**: Tracks all system activities (searches, access, admin actions)
- **error_log**: Application error tracking with stack traces
- **access_attempts**: Failed access tracking for security monitoring

### Cache Tables
- **genesys_groups/locations/skills**: Cached Genesys Cloud data with automatic refresh
- **search_cache**: Cached search results for performance
- **user_sessions**: Active user session management

## Configuration Management

### Overview
The application supports storing ALL configuration in the database with encryption for sensitive values:
- Runtime configuration changes without restarting
- Encrypted storage for passwords, secrets, and sensitive data
- Audit trail of all configuration changes
- Centralized configuration management

### Encrypted Configuration
Sensitive values are encrypted using Fernet symmetric encryption (from the `cryptography` library):
- Encryption key is stored in `CONFIG_ENCRYPTION_KEY` environment variable
- Sensitive values are stored in the `encrypted_value` column as BYTEA
- Non-sensitive values use the plain `setting_value` column
- The system automatically encrypts/decrypts based on the `is_sensitive` flag

### Migration Process
1. Add `CONFIG_ENCRYPTION_KEY` to your `.env` file (generate one if needed)
2. Run the migration script: `python scripts/migrate_config_to_db.py`
3. Update your `.env` to contain only database connection and encryption key
4. All other configuration will be loaded from the database

### What's Stored in Database

**Encrypted Values** (stored in `encrypted_value` column):
- User access lists (auth.viewers, auth.editors, auth.admins)
- Flask secret key (flask.secret_key)
- LDAP credentials (ldap.bind_dn, ldap.bind_password)
- Genesys credentials (genesys.client_id, genesys.client_secret)
- Graph credentials (graph.client_id, graph.client_secret, graph.tenant_id)

**Plain Values** (stored in `setting_value` column):
- Flask settings (host, port, debug mode)
- LDAP settings (host, port, SSL, base DN, timeouts)
- Genesys settings (region, API timeout, cache refresh period)
- Graph settings (API timeout)
- Search settings (overall timeout)

### Configuration Categories
- **auth**: User access control lists (encrypted)
- **flask**: Flask application settings
- **ldap**: LDAP/Active Directory settings
- **genesys**: Genesys Cloud settings (includes 6-hour cache refresh default)
- **graph**: Microsoft Graph API settings
- **search**: Search functionality settings

### Managing Configuration
```sql
-- View all configuration (sensitive values shown as '***')
SELECT category, setting_key, 
       CASE WHEN is_sensitive THEN '***ENCRYPTED***' ELSE setting_value END as value,
       is_sensitive, description
FROM configuration
ORDER BY category, setting_key;

-- View configuration history
SELECT * FROM configuration_history
ORDER BY changed_at DESC
LIMIT 20;

-- Update a non-sensitive value
UPDATE configuration 
SET setting_value = 'new_value', updated_by = 'admin@example.com'
WHERE category = 'flask' AND setting_key = 'debug';

-- For sensitive values, use the application's configuration service
-- to ensure proper encryption
```

## Troubleshooting

### Common Issues

#### Missing api_tokens table
If you get errors about `api_tokens` table not existing:
```bash
psql -U whodis_user -d whodis_db -h localhost -f database/create_tables.sql
```

#### Column name error in pg_stat_user_tables
The error about `tablename` not existing is because PostgreSQL system views vary by version. The code has been updated to use `pg_class` which is more reliable.

#### Transaction poisoning (InFailedSqlTransaction)
If you get "InFailedSqlTransaction" errors:
1. Restart your Flask application
2. Make sure all tables exist (run create_tables.sql)
3. The updated code includes proper error handling to prevent this

#### Check what tables exist
```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```

## Maintenance

### View Audit Logs
```sql
-- Recent searches
SELECT * FROM audit_log 
WHERE event_type = 'search' 
ORDER BY timestamp DESC 
LIMIT 10;

-- Failed access attempts
SELECT * FROM access_attempts 
WHERE access_granted = FALSE 
ORDER BY timestamp DESC 
LIMIT 10;

-- Error summary
SELECT error_type, COUNT(*) as count 
FROM error_log 
GROUP BY error_type 
ORDER BY count DESC;

-- Token status
SELECT service_name, expires_at, 
       CASE WHEN expires_at > NOW() THEN 'Valid' ELSE 'Expired' END as status
FROM api_tokens;
```

### Clean Up Old Data
```sql
-- Run the cleanup function (removes data older than configured retention)
SELECT cleanup_old_data();

-- Or set up a cron job to run it daily
-- Add to crontab: 0 2 * * * psql -U whodis_user -d whodis_db -c "SELECT cleanup_old_data();"
```

### Backup and Restore
```bash
# Backup database
pg_dump -U whodis_user -h localhost whodis_db > backup_$(date +%Y%m%d).sql

# Restore database
psql -U whodis_user -h localhost whodis_db < backup_20240101.sql

# Backup only specific tables
pg_dump -U whodis_user -h localhost -t audit_log -t configuration whodis_db > partial_backup.sql
```

## Performance Tuning

### PostgreSQL Configuration
Add to `postgresql.conf`:

```conf
# Connection pooling
max_connections = 200
shared_buffers = 256MB

# Query performance
effective_cache_size = 1GB
work_mem = 4MB

# Logging (for development)
log_statement = 'all'
log_duration = on
```

### Monitor Performance
```sql
-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check slow queries (requires pg_stat_statements extension)
SELECT query, calls, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan;

-- Check for missing indexes
SELECT 
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch
FROM pg_stat_user_tables
WHERE seq_scan > idx_scan
ORDER BY seq_scan DESC;
```

### Optimize Queries
```sql
-- Analyze tables for query planner
ANALYZE;

-- Vacuum to reclaim space
VACUUM ANALYZE;

-- Reindex if needed
REINDEX DATABASE whodis_db;
```