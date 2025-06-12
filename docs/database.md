# WhoDis Database Documentation

## Table of Contents
- [Initial Setup](#initial-setup)
- [Consolidated Architecture](#consolidated-architecture)
- [Table Descriptions](#table-descriptions)
- [Configuration Management](#configuration-management)
- [Session Management](#session-management)
- [Migration from Legacy Tables](#migration-from-legacy-tables)
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
WHODIS_ENCRYPTION_KEY=your_encryption_key_here
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
-- api_tokens, users, configuration, configuration_history, audit_log, 
-- error_log, access_attempts, genesys_groups, genesys_locations,
-- genesys_skills, search_cache, user_sessions, user_notes, employee_profiles
```

## Consolidated Architecture

WhoDis uses a **consolidated employee data architecture** that centralizes employee information management:

### Core Principle
All employee profile data, photos, and Keystone information are now stored in a single `employee_profiles` table instead of separate legacy tables (`graph_photos`, `data_warehouse_cache`).

### Benefits
- **Unified Data Model**: Single source of truth for employee information
- **Simplified Queries**: No complex joins across multiple tables  
- **Better Performance**: Fewer database operations and improved caching
- **Easier Maintenance**: Single table to backup, migrate, and optimize
- **Atomic Updates**: Employee data changes are transactional

### Architecture Components

#### 1. Employee Profiles Service (`refresh_employee_profiles.py`)
- **Purpose**: Central service for all employee data operations
- **Responsibilities**: 
  - Data warehouse integration (Keystone queries)
  - Microsoft Graph photo fetching
  - Profile creation and updates
  - Cache management and statistics

#### 2. Consolidated Storage (`employee_profiles` table)
- **UPN**: Primary key and unique identifier
- **Keystone Data**: User serial, login times, roles, job codes
- **Photos**: Base64 photo data with content type
- **Metadata**: Created/updated timestamps, raw JSON data

#### 3. Legacy Migration
- **Status**: Legacy tables `graph_photos` and `data_warehouse_cache` have been removed
- **Migration Tool**: Use `scripts/drop_legacy_tables.py` to clean up existing installations
- **Data Safety**: All data was migrated to `employee_profiles` before removal

## Migration from Legacy Tables

### For Existing Installations (Pre-2.0)

If you're upgrading from a previous version that used separate `graph_photos` and `data_warehouse_cache` tables:

#### 1. Backup Your Database
```bash
pg_dump -U whodis_user -h localhost whodis_db > backup_before_migration_$(date +%Y%m%d).sql
```

#### 2. Run Migration Script
```bash
# Preview what will be changed
python scripts/drop_legacy_tables.py --dry-run

# Execute the migration
python scripts/drop_legacy_tables.py
```

#### 3. Verify Migration
```bash
# Check employee profiles are populated
python scripts/refresh_employee_profiles.py refresh

# Run comprehensive verification
python scripts/verify_deployment.py
```

#### 4. Post-Migration Cleanup
The migration script will:
- ✅ Verify `employee_profiles` table exists and has data
- ✅ Drop `graph_photos` and `data_warehouse_cache` tables
- ✅ Update PostgreSQL statistics with `ANALYZE`
- ✅ Provide detailed logging of all operations

### For New Installations (2.0+)
No migration needed - the consolidated architecture is used from the start.

### 4. Initial Table Analysis

For new installations, run ANALYZE to update PostgreSQL statistics:

```bash
psql -U postgres -d whodis_db -h localhost -f database/analyze_tables.sql
```

This prevents the `-1` row count issue in the admin interface.

## Table Descriptions

### Core Tables (with Base Model Structure)
- **api_tokens** (extends CacheableModel): Stores API tokens with automatic expiration tracking
  - Includes: `created_at`, `updated_at`, `expires_at` with automatic cleanup
- **users** (extends BaseModel + TimestampMixin): User authentication and authorization
  - Includes: `created_at`, `updated_at` with automatic timestamp management
- **user_notes** (extends BaseModel + TimestampMixin): Internal notes about users
  - Includes: `created_at`, `updated_at` for audit trail
- **configuration**: Database-stored configuration values with encryption support
- **configuration_history**: Audit trail of all configuration changes

### Audit & Logging Tables (using AuditableModel)
- **audit_log** (extends AuditableModel): Tracks all system activities
  - Base fields: `created_at`, `updated_at`, `user_email`, `ip_address`, `user_agent`, `session_id`, `success`, `message`, `additional_data`
  - Custom fields: `event_type`, `action`, `target_resource`, `search_query`, `search_results_count`, `search_services`
  - Note: Uses actual separate table, not unified model
- **error_log** (extends AuditableModel): Application error tracking
  - Base fields: `created_at`, `updated_at`, `user_email`, `ip_address`, `user_agent`, `session_id`, `success`, `message`, `additional_data`
  - Custom fields: `error_type`, `stack_trace`, `severity`, `request_path`, `request_method`
  - Note: Uses actual separate table, not unified model
- **access_attempts** (extends AuditableModel): Security monitoring
  - Base fields: `created_at`, `updated_at`, `user_email`, `ip_address`, `user_agent`, `session_id`, `success`, `message`, `additional_data`
  - Custom fields: `requested_path`, `auth_method`
  - Note: `success` field represents access_granted, `message` field represents denial_reason

### Cache & External Data Tables
- **search_cache** (extends CacheableModel): Search result caching
  - Includes automatic expiration management
- **graph_photos** (extends CacheableModel): User photos with 30-day expiration
  - Includes `expires_at` for automatic cleanup
- **genesys_groups/locations/skills** (extends ServiceDataModel): Genesys data cache
  - Includes: `service_id`, `service_name`, `is_active`, `created_at`, `updated_at`
- **user_sessions** (extends BaseModel + TimestampMixin + ExpirableMixin): Session management
  - Includes automatic expiration and activity tracking

## Configuration Management

### Overview
The application supports storing ALL configuration in the database with encryption for sensitive values:
- Runtime configuration changes without restarting
- Encrypted storage for passwords, secrets, and sensitive data
- Audit trail of all configuration changes
- Centralized configuration management

### Encrypted Configuration
Sensitive values are encrypted using Fernet symmetric encryption (from the `cryptography` library):
- Encryption key is stored in `WHODIS_ENCRYPTION_KEY` environment variable
- Sensitive values are stored in the `encrypted_value` column as BYTEA
- Non-sensitive values use the plain `setting_value` column
- The system automatically encrypts/decrypts based on the `is_sensitive` flag

### Migration Process
1. Add `WHODIS_ENCRYPTION_KEY` to your `.env` file (generate one if needed)
2. Run the migration script: `python scripts/migrate_config_to_db.py`
3. Update your `.env` to contain only database connection and encryption key
4. All other configuration will be loaded from the database

### What's Stored in Database

**Encrypted Values** (stored in `encrypted_value` column):
- ~~User access lists (auth.viewers, auth.editors, auth.admins)~~ **DEPRECATED** - Use `users` table instead
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
- **session**: Session timeout settings (15min timeout, 2min warning, 30s check interval)

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

## Session Management

### Overview
WhoDis implements session timeout with inactivity warnings to enhance security, especially for shared workstations or kiosk deployments. Sessions automatically expire after a configurable period of inactivity with a warning modal before timeout.

### Features
- **Configurable Timeout**: Default 15 minutes, adjustable via database configuration
- **Warning Modal**: Shows 2 minutes before timeout with countdown timer
- **Activity Tracking**: Mouse, keyboard, scroll, and touch events reset the timer
- **Session Extension**: Users can extend their session from the warning modal
- **Automatic Cleanup**: Expired sessions are cleaned up on application startup
- **SSO Integration**: Seamless re-authentication through Azure AD

### Session Configuration
```sql
-- View current session settings
SELECT setting_key, setting_value, description 
FROM configuration 
WHERE category = 'session';

-- Update session timeout (in minutes)
UPDATE configuration 
SET setting_value = '30', updated_by = 'admin@example.com'
WHERE category = 'session' AND setting_key = 'timeout_minutes';

-- Update warning time (in minutes before timeout)
UPDATE configuration 
SET setting_value = '5', updated_by = 'admin@example.com'
WHERE category = 'session' AND setting_key = 'warning_minutes';
```

### Session Table Structure
The `user_sessions` table tracks active sessions:
- **id**: Unique session identifier (secure random token)
- **user_email**: Associated user
- **ip_address**: Client IP for security tracking
- **user_agent**: Browser information
- **created_at**: Session start time
- **last_activity**: Last recorded activity
- **expires_at**: When session will expire
- **warning_shown**: Whether timeout warning has been displayed
- **is_active**: Session active status

### Monitoring Sessions
```sql
-- View active sessions
SELECT user_email, ip_address, last_activity, expires_at,
       EXTRACT(EPOCH FROM (expires_at - NOW()))/60 as minutes_remaining
FROM user_sessions
WHERE is_active = TRUE AND expires_at > NOW()
ORDER BY last_activity DESC;

-- View sessions about to expire
SELECT user_email, expires_at, warning_shown
FROM user_sessions
WHERE is_active = TRUE 
  AND expires_at > NOW() 
  AND expires_at < NOW() + INTERVAL '5 minutes'
ORDER BY expires_at;

-- Clean up expired sessions manually
DELETE FROM user_sessions WHERE expires_at < NOW();
```

### Session API Endpoints
- **GET /api/session/config**: Get timeout configuration
- **POST /api/session/check**: Check session validity and update activity
- **POST /api/session/extend**: Extend current session
- **POST /logout**: End session and logout

### Troubleshooting Sessions
1. **Session not timing out**: Check if JavaScript is loaded and activity events are being tracked
2. **Warning not showing**: Verify `warning_minutes` is less than `timeout_minutes`
3. **Immediate logout**: Check if session table has required columns (run migration if needed)

## Troubleshooting

### Common Issues

#### Missing api_tokens table
If you get errors about `api_tokens` table not existing:
```bash
psql -U whodis_user -d whodis_db -h localhost -f database/create_tables.sql
```

#### Column name error in pg_stat_user_tables
The error about `tablename` not existing is because PostgreSQL system views vary by version. The code has been updated to use `pg_class` which is more reliable.

#### Table showing -1 row count in Admin UI
This happens when PostgreSQL hasn't analyzed new tables yet. Fix by running:
```bash
psql -U postgres -d whodis_db -h localhost -f database/analyze_tables.sql
```
PostgreSQL's autovacuum will handle this automatically going forward.

#### Missing columns error for user_sessions
If you get errors about `warning_shown` or `is_active` columns:
```bash
# Run the Python migration script
python scripts/add_session_timeout_columns.py
```

#### Missing 'message' column in audit tables
If you get errors about missing 'message' column in audit_log, error_log, or access_attempts:
1. This was fixed in June 2025 - tables now include all AuditableModel base fields
2. The create_tables.sql file has been updated with the correct schema
3. For existing installations, schema fix scripts are archived in scripts/archive/2025-06-schema-fixes/

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

-- Active sessions summary
SELECT COUNT(*) as active_sessions,
       MIN(created_at) as oldest_session,
       MAX(last_activity) as most_recent_activity
FROM user_sessions
WHERE is_active = TRUE AND expires_at > NOW();
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