# WhoDis Troubleshooting Guide

This guide provides comprehensive troubleshooting solutions for common issues in WhoDis. Issues are organized by category for quick reference.

## Table of Contents
- [Quick Diagnostics](#quick-diagnostics)
- [Installation and Setup Issues](#installation-and-setup-issues)
- [Database Problems](#database-problems)
- [Authentication and Access Issues](#authentication-and-access-issues)
- [Search and Performance Issues](#search-and-performance-issues)
- [Configuration Problems](#configuration-problems)
- [API Integration Issues](#api-integration-issues)
- [Cache and Token Problems](#cache-and-token-problems)
- [UI and Display Issues](#ui-and-display-issues)
- [Job Role Compliance Issues](#job-role-compliance-issues)
- [Logging and Auditing Issues](#logging-and-auditing-issues)
- [Production Deployment Issues](#production-deployment-issues)

## Quick Diagnostics

### Run Diagnostic Scripts

```bash
# Check overall system status
python scripts/check_config_status.py

# Verify encryption configuration
python scripts/verify_encrypted_config.py

# Diagnose configuration problems
python scripts/diagnose_config.py

# Test Genesys cache
python scripts/check_genesys_cache.py
```

### Check Logs

```bash
# Application logs
tail -50 /var/log/whodis/error.log

# Nginx logs (if using reverse proxy)
tail -50 /var/log/nginx/whodis.error.log

# PostgreSQL logs
tail -50 /var/log/postgresql/postgresql-*.log

# Check recent audit logs in database
psql -U whodis_user -d whodis_db -c "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10;"
```

### Verify Services

```bash
# Check application is running
ps aux | grep gunicorn

# Check database connection
psql -U whodis_user -d whodis_db -h localhost -c "SELECT 1;"

# Check web server
curl -I http://localhost:5000/
```

## Installation and Setup Issues

### Issue: "ModuleNotFoundError" when running application

**Symptoms:**
```
ModuleNotFoundError: No module named 'flask'
```

**Cause:** Dependencies not installed or wrong Python environment

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -i flask
```

---

### Issue: "Permission denied" when creating directories

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: '/var/log/whodis'
```

**Cause:** User doesn't have write permissions

**Solution:**
```bash
# Create log directory with proper permissions
sudo mkdir -p /var/log/whodis
sudo chown whodis:whodis /var/log/whodis
sudo chmod 755 /var/log/whodis

# Or run from user directory
mkdir -p ~/whodis/logs
# Update supervisor config to use this path
```

---

### Issue: PostgreSQL tables not created

**Symptoms:** Application starts but shows errors about missing tables

**Cause:** Database schema not applied

**Solution:**
```bash
# Run table creation script
psql -U whodis_user -d whodis_db -h localhost -f database/create_tables.sql

# Verify tables exist
psql -U whodis_user -d whodis_db -c "\dt"

# Run ANALYZE for proper statistics
psql -U postgres -d whodis_db -h localhost -f database/analyze_tables.sql
```

## Database Problems

### Issue: "Connection refused" to PostgreSQL

**Symptoms:**
```
psycopg2.OperationalError: connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

**Diagnosis:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check PostgreSQL is listening
sudo netstat -plnt | grep 5432

# Check pg_hba.conf allows connection
sudo cat /etc/postgresql/12/main/pg_hba.conf | grep whodis
```

**Solution:**
```bash
# Start PostgreSQL if stopped
sudo systemctl start postgresql
sudo systemctl enable postgresql

# If pg_hba.conf missing entry, add:
sudo nano /etc/postgresql/12/main/pg_hba.conf
# Add: host    whodis_db    whodis_user    127.0.0.1/32    md5

# Reload PostgreSQL
sudo systemctl reload postgresql
```

---

### Issue: "authentication failed for user"

**Symptoms:**
```
psycopg2.OperationalError: FATAL: password authentication failed for user "whodis_user"
```

**Cause:** Wrong password in .env or user doesn't exist

**Solution:**
```bash
# Verify user exists
sudo -u postgres psql -c "\du" | grep whodis_user

# If user doesn't exist, create it
sudo -u postgres psql <<EOF
CREATE USER whodis_user WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE whodis_db TO whodis_user;
EOF

# Verify .env has correct password
cat .env | grep POSTGRES_PASSWORD

# Test connection manually
psql -U whodis_user -d whodis_db -h localhost -c "SELECT 1;"
```

---

### Issue: Slow database queries

**Symptoms:** Admin pages load slowly, searches take > 5 seconds

**Diagnosis:**
```sql
-- Check slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check table sizes
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public' AND n_distinct > 100
ORDER BY n_distinct DESC;
```

**Solution:**
```bash
# Run VACUUM ANALYZE
psql -U whodis_user -d whodis_db -c "VACUUM ANALYZE;"

# For severe fragmentation (requires downtime)
psql -U whodis_user -d whodis_db -c "VACUUM FULL;"

# Check for N+1 queries in code
# Example fix: Use joinedload() or bulk queries instead of individual lookups

# Increase PostgreSQL memory if needed
sudo nano /etc/postgresql/12/main/postgresql.conf
# shared_buffers = 256MB
# effective_cache_size = 1GB
sudo systemctl restart postgresql
```

## Authentication and Access Issues

### Issue: "Access denied" even though user is authenticated

**Symptoms:** User logs in successfully but sees "Access denied" messages

**Diagnosis:**
```sql
-- Check user role in database
SELECT email, role, is_active FROM users WHERE email = 'user@example.com';

-- Check recent access attempts
SELECT * FROM access_attempts
WHERE user_email = 'user@example.com'
ORDER BY timestamp DESC
LIMIT 10;
```

**Solution:**
```bash
# User not in database - they'll be auto-provisioned on first login
# Check configuration for default role

# Or manually add user with appropriate role
python <<EOF
from app import create_app
from app.models.user import User
app = create_app()
with app.app_context():
    user = User(email='user@example.com', role='viewer', is_active=True)
    user.save()
    print(f"Created user: {user.email} with role: {user.role}")
EOF
```

---

### Issue: Azure AD SSO not working

**Symptoms:** Users aren't redirected to Azure AD login or authentication fails

**Diagnosis:**
```bash
# Check if Azure AD headers are being passed
curl -I https://whodis.example.com/ | grep X-MS-CLIENT

# Check nginx/Apache proxy configuration
sudo cat /etc/nginx/sites-available/whodis | grep X-MS-CLIENT

# Check application logs
tail -50 /var/log/whodis/error.log | grep -i auth
```

**Solution:**
```bash
# Ensure nginx/Apache is forwarding Azure AD headers
# In nginx.conf:
proxy_set_header X-MS-CLIENT-PRINCIPAL-NAME $http_x_ms_client_principal_name;
proxy_set_header X-MS-CLIENT-PRINCIPAL-ID $http_x_ms_client_principal_id;

# Reload nginx
sudo systemctl reload nginx

# For Azure App Service, ensure Easy Auth is enabled
# Portal → App Service → Authentication → Add identity provider → Microsoft
```

---

### Issue: Session timeout not working

**Symptoms:** Users aren't warned before timeout or sessions never expire

**Diagnosis:**
```sql
-- Check session configuration
SELECT category, key, value FROM configuration WHERE category = 'session';

-- Check active sessions
SELECT user_email, created_at, expires_at, is_expired
FROM sessions
WHERE user_email = 'user@example.com'
ORDER BY created_at DESC;
```

**Solution:**
```python
# Set session timeout via admin UI or script
from app.services.simple_config import config_set

config_set("session", "timeout_minutes", "15")
config_set("session", "warning_minutes", "2")
config_set("session", "extend_on_activity", "true")
```

## Search and Performance Issues

### Issue: Search returns no results for valid user

**Symptoms:** Searching for a known user returns "No results found"

**Diagnosis:**
```bash
# Check service connectivity
python scripts/diagnose_config.py

# Check recent searches in audit log
psql -U whodis_user -d whodis_db -c "
SELECT search_query, results_count, services, timestamp
FROM audit_log
WHERE event_type = 'search' AND search_query LIKE '%username%'
ORDER BY timestamp DESC
LIMIT 5;"
```

**Solution:**
```bash
# Test LDAP connection manually
ldapsearch -H ldaps://dc.example.com:636 \
  -D "CN=WhoDis Service,OU=Service Accounts,DC=example,DC=com" \
  -W \
  -b "DC=example,DC=com" \
  "(mail=user@example.com)"

# Check API credentials are correct
python scripts/check_config_status.py

# Refresh API tokens
# Via admin UI: /admin/cache → Refresh buttons

# Check search cache isn't stale
psql -U whodis_user -d whodis_db -c "DELETE FROM search_cache WHERE is_expired = true;"
```

---

### Issue: Search is very slow (> 10 seconds)

**Symptoms:** Every search takes a long time, UI becomes unresponsive

**Diagnosis:**
```bash
# Check which service is slow
# Add timing to logs temporarily
tail -f /var/log/whodis/access.log | grep "search"

# Check API token status
curl -s https://whodis.example.com/admin/cache | grep -i token

# Check database connection pool
psql -U whodis_user -d whodis_db -c "
SELECT count(*), state
FROM pg_stat_activity
WHERE datname = 'whodis_db'
GROUP BY state;"
```

**Solution:**
```bash
# Refresh expired API tokens
# Via admin UI: /admin/cache → click "Refresh" on expired tokens

# Clear old cache entries
psql -U whodis_user -d whodis_db -c "DELETE FROM search_cache WHERE expires_at < NOW();"

# Check network latency to external services
ping dc.example.com
ping api.mypurecloud.com

# Increase timeout values if needed (default LDAP: 3s, Graph: 4s, Genesys: 5s)
# Via admin UI: /admin/configuration → search category

# Check concurrent request handling
# Increase gunicorn workers if CPU allows
# In supervisor config: --workers 4 (or more)
```

---

### Issue: Multiple result selection not working

**Symptoms:** When multiple users match, selection interface doesn't appear

**Diagnosis:**
```bash
# Check JavaScript console for errors
# Open browser DevTools → Console

# Check HTMX is loaded
curl -s https://whodis.example.com/ | grep htmx

# Check audit log for multiple results
psql -U whodis_user -d whodis_db -c "
SELECT search_query, results_count, additional_data
FROM audit_log
WHERE event_type = 'search' AND results_count > 1
ORDER BY timestamp DESC
LIMIT 5;"
```

**Solution:**
```bash
# Clear browser cache
# Ctrl+Shift+R (hard refresh)

# Verify HTMX CDN is accessible
curl -I https://unpkg.com/htmx.org

# Check for JavaScript errors in templates
# Ensure escapeHtml() is used properly
```

## Configuration Problems

### Issue: "WHODIS_ENCRYPTION_KEY must be set" error

**Symptoms:**
```
ValueError: WHODIS_ENCRYPTION_KEY must be set in environment variables
```

**Cause:** Encryption key not set in .env file

**Solution:**
```bash
# Generate new encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Add to .env file
echo "WHODIS_ENCRYPTION_KEY=<generated-key>" >> .env

# Ensure .env is in the right location and readable
chmod 600 .env
cat .env | grep WHODIS_ENCRYPTION_KEY

# If changing key, you'll need to re-encrypt all configuration
# BACKUP FIRST!
python scripts/export_config.py > config_backup.json
```

---

### Issue: "Error decrypting configuration" messages

**Symptoms:**
```
ERROR: Failed to decrypt configuration value for flask.secret_key
```

**Cause:** Encryption key changed or salt file missing/corrupted

**Diagnosis:**
```bash
# Check encryption key is set
echo $WHODIS_ENCRYPTION_KEY

# Check salt file exists
ls -la .whodis_salt

# Verify encrypted config script
python scripts/verify_encrypted_config.py
```

**Solution:**
```bash
# If salt file is missing and you have backup
cp /secure/backup/.whodis_salt.backup .whodis_salt
chmod 600 .whodis_salt

# If encryption key changed, restore old key
# Or re-encrypt all configuration with new key (requires reconfiguration)

# If configuration is corrupted, restore from backup
python scripts/export_config.py  # On working system
# Then on broken system:
# Manually re-enter configuration via admin UI
```

---

### Issue: Configuration changes not taking effect

**Symptoms:** Changes made via admin UI don't apply to application

**Cause:** Application needs restart or configuration cached

**Solution:**
```bash
# Restart application
sudo supervisorctl restart whodis

# Or if using systemd
sudo systemctl restart whodis

# Clear any application-level caching
# Via admin UI: /admin/cache → Clear Cache

# Verify configuration was saved
psql -U whodis_user -d whodis_db -c "
SELECT category, key, value, updated_at
FROM configuration
ORDER BY updated_at DESC
LIMIT 10;"
```

## API Integration Issues

### Issue: LDAP connection timeout

**Symptoms:**
```
ERROR: LDAP connection timeout after 3 seconds
```

**Diagnosis:**
```bash
# Test LDAP connectivity manually
ldapsearch -H ldaps://dc.example.com:636 \
  -D "CN=WhoDis Service,OU=Service Accounts,DC=example,DC=com" \
  -W \
  -b "DC=example,DC=com" \
  "(objectClass=user)" \
  -LLL dn

# Check firewall rules
sudo ufw status | grep 636

# Check network latency
ping dc.example.com
```

**Solution:**
```bash
# Increase LDAP timeout in configuration
# Via admin UI: /admin/configuration → ldap category
# Set ldap.timeout_seconds = 10

# Check LDAP server isn't overloaded
# Contact AD administrators

# Verify SSL certificate if using LDAPS
openssl s_client -connect dc.example.com:636 -showcerts
```

---

### Issue: Genesys API returning 401 Unauthorized

**Symptoms:**
```
ERROR: Genesys API authentication failed: 401 Unauthorized
```

**Diagnosis:**
```bash
# Check Genesys token status
curl -s https://whodis.example.com/admin/cache | grep -i genesys

# Check configuration
psql -U whodis_user -d whodis_db -c "
SELECT category, key FROM configuration WHERE category = 'genesys';"

# Test Genesys API manually
python scripts/check_genesys_cache.py
```

**Solution:**
```bash
# Refresh Genesys token
# Via admin UI: /admin/cache → click "Refresh" on Genesys token

# Verify Genesys credentials are correct
# Via admin UI: /admin/configuration → genesys category
# Check client_id, client_secret, org_id

# Check Genesys OAuth token endpoint is accessible
curl -I https://login.mypurecloud.com/oauth/token
```

---

### Issue: Microsoft Graph API rate limiting

**Symptoms:**
```
ERROR: Graph API throttled: 429 Too Many Requests
```

**Cause:** Too many requests to Graph API, hitting rate limits

**Solution:**
```bash
# Increase cache TTL to reduce API calls
# Via admin UI: /admin/configuration → graph category
# Increase cache expiration time

# Implement exponential backoff (already implemented in base service)
# Check retry logic is working

# Check employee profiles cache is being used
psql -U whodis_user -d whodis_db -c "
SELECT COUNT(*), MAX(updated_at)
FROM employee_profiles;"

# Refresh employee profiles cache
python scripts/refresh_employee_profiles.py refresh

# Reduce concurrent requests if needed
# Decrease gunicorn workers temporarily
```

## Cache and Token Problems

### Issue: API tokens not refreshing automatically

**Symptoms:** Tokens expire and aren't renewed, searches fail

**Diagnosis:**
```sql
-- Check token status
SELECT service_name, expires_at, is_expired
FROM api_tokens
ORDER BY expires_at;

-- Check token refresh service logs
```

**Solution:**
```bash
# Manually refresh tokens
# Via admin UI: /admin/cache → Refresh buttons

# Restart token refresh background service
sudo supervisorctl restart whodis

# Check background service is running
ps aux | grep token_refresh

# Verify token refresh service configuration
# Should refresh every 5 minutes automatically
```

---

### Issue: Search cache showing stale results

**Symptoms:** Search results don't reflect recent changes to user data

**Cause:** Cache not expiring or TTL too long

**Solution:**
```bash
# Clear all search cache
psql -U whodis_user -d whodis_db -c "DELETE FROM search_cache;"

# Clear expired cache only
psql -U whodis_user -d whodis_db -c "DELETE FROM search_cache WHERE is_expired = true;"

# Adjust cache TTL if needed (default: 30 minutes)
# Via admin UI: /admin/configuration → search category
# Set search.cache_ttl_minutes

# Force cache refresh for specific user
# Search again with Ctrl+Shift+R (hard refresh in browser)
```

---

### Issue: Genesys cache not populating

**Symptoms:** Genesys groups, skills, or locations not showing in admin UI

**Diagnosis:**
```bash
# Check Genesys cache tables
psql -U whodis_user -d whodis_db -c "
SELECT 'groups' as type, COUNT(*) FROM genesys_groups
UNION ALL
SELECT 'skills', COUNT(*) FROM genesys_skills
UNION ALL
SELECT 'locations', COUNT(*) FROM genesys_locations;"

# Test Genesys cache manually
python scripts/check_genesys_cache.py
```

**Solution:**
```bash
# Manually refresh Genesys cache
# Via admin UI: /admin/cache → Refresh Genesys Cache

# Check Genesys API credentials
python scripts/diagnose_config.py

# Verify Genesys token is valid
# Via admin UI: /admin/cache → check token expiration

# Check cache service logs for errors
tail -50 /var/log/whodis/error.log | grep -i genesys
```

## UI and Display Issues

### Issue: Profile photos not loading

**Symptoms:** User photos show placeholder instead of actual photo

**Diagnosis:**
```sql
-- Check employee profiles cache
SELECT email, has_photo, photo_updated_at
FROM employee_profiles
WHERE email = 'user@example.com';
```

**Solution:**
```bash
# Refresh employee profiles with photos
python scripts/refresh_employee_profiles.py refresh

# Check Graph API permissions
# Needs User.Read.All or similar permission

# Verify Graph token is valid
# Via admin UI: /admin/cache → check Microsoft Graph token

# Check photo data in database
psql -U whodis_user -d whodis_db -c "
SELECT email, length(photo_data) as photo_size, photo_content_type
FROM employee_profiles
WHERE email = 'user@example.com';"

# If photo_data is NULL, Graph API might not have photo
# Photos are fetched from Microsoft Graph /photo endpoint
```

---

### Issue: Session timeout warning not appearing

**Symptoms:** Users are logged out without warning

**Diagnosis:**
```bash
# Check session configuration
psql -U whodis_user -d whodis_db -c "
SELECT * FROM configuration WHERE category = 'session';"

# Check JavaScript console for errors
# Browser DevTools → Console

# Verify session timeout JavaScript is loaded
curl -s https://whodis.example.com/ | grep -i session
```

**Solution:**
```bash
# Ensure session timeout is configured
# Via admin UI: /admin/configuration → session category
# timeout_minutes: 15
# warning_minutes: 2

# Clear browser cache
# Ctrl+Shift+R

# Check session JavaScript file is accessible
curl -I https://whodis.example.com/static/js/session-timeout.js
```

---

### Issue: HTMX updates not working

**Symptoms:** Dynamic content doesn't update, page requires full refresh

**Diagnosis:**
```bash
# Check browser console for HTMX errors
# DevTools → Console

# Verify HTMX is loaded
curl -s https://whodis.example.com/ | grep htmx

# Check Content Security Policy isn't blocking HTMX
curl -I https://whodis.example.com/ | grep -i content-security-policy
```

**Solution:**
```bash
# Ensure HTMX CDN is accessible
# Check base.html template has:
# <script src="https://unpkg.com/htmx.org@1.9.x"></script>

# Update CSP to allow HTMX
# In nginx.conf or security_headers.py:
# script-src 'self' 'unsafe-inline' https://unpkg.com

# Clear browser cache and hard refresh
# Ctrl+Shift+R
```

## Job Role Compliance Issues

### Issue: Job codes table shows -1 mapping count

**Symptoms:** Admin UI shows "-1" for role mapping counts

**Cause:** PostgreSQL statistics not updated

**Solution:**
```bash
# Run ANALYZE on affected tables
psql -U postgres -d whodis_db -c "ANALYZE job_codes;"
psql -U postgres -d whodis_db -c "ANALYZE job_role_mappings;"
psql -U postgres -d whodis_db -c "ANALYZE system_roles;"

# Refresh admin page
```

---

### Issue: Data warehouse sync failing

**Symptoms:**
```
ERROR: Failed to connect to data warehouse
```

**Diagnosis:**
```bash
# Check data warehouse configuration
psql -U whodis_user -d whodis_db -c "
SELECT category, key FROM configuration WHERE category = 'warehouse';"

# Test warehouse connection manually
# Use pyodbc or SQL Server client
```

**Solution:**
```bash
# Verify warehouse credentials
# Via admin UI: /admin/configuration → warehouse category

# Check firewall allows connection to SQL Server
sudo ufw status | grep 1433

# Test connection with sqlcmd or Azure Data Studio
sqlcmd -S warehouse.example.com -U whodis_reader -P password -Q "SELECT @@VERSION"

# Check warehouse service account has read permissions
```

---

### Issue: Compliance matrix takes forever to load

**Symptoms:** Browser becomes unresponsive when loading compliance matrix

**Cause:** Too many mappings being rendered at once

**Solution:**
```bash
# Use client-side filtering (already implemented in v2.1.0+)
# Filter by department or system before loading

# Check for N+1 queries
# Run ANALYZE on tables
psql -U postgres -d whodis_db -c "ANALYZE job_role_mappings;"

# Implement progressive loading if not already enabled
# "Load More" button should appear for large datasets
```

## Logging and Auditing Issues

### Issue: Audit logs not being created

**Symptoms:** No entries in audit_log table despite user activity

**Diagnosis:**
```sql
-- Check audit log table exists
SELECT COUNT(*) FROM audit_log;

-- Check recent audit entries
SELECT event_type, COUNT(*) FROM audit_log
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY event_type;

-- Check error logs
SELECT * FROM error_log ORDER BY timestamp DESC LIMIT 10;
```

**Solution:**
```bash
# Verify audit service is working
# Check application logs
tail -50 /var/log/whodis/error.log | grep -i audit

# Ensure audit service is initialized
# Check app/__init__.py initialization

# Restart application
sudo supervisorctl restart whodis

# Test audit logging manually
# Perform a search and check audit_log table
```

---

### Issue: Log files growing too large

**Symptoms:** Disk space running out, log files in GB range

**Solution:**
```bash
# Check log sizes
du -sh /var/log/whodis/*
du -sh /var/log/nginx/*
du -sh /var/log/postgresql/*

# Set up log rotation (if not already configured)
sudo nano /etc/logrotate.d/whodis

# Compress old audit logs
psql -U whodis_user -d whodis_db -c "
DELETE FROM audit_log WHERE timestamp < NOW() - INTERVAL '90 days';"

# Vacuum database after large deletes
psql -U whodis_user -d whodis_db -c "VACUUM FULL audit_log;"
```

## Production Deployment Issues

### Issue: Application won't start with gunicorn

**Symptoms:**
```
ERROR: No such file or directory: 'gunicorn'
```

**Solution:**
```bash
# Ensure gunicorn is installed in venv
source venv/bin/activate
pip install gunicorn

# Verify gunicorn path in supervisor config
which gunicorn
# Should be: /home/whodis/whodis/venv/bin/gunicorn

# Update supervisor config with full path
sudo nano /etc/supervisor/conf.d/whodis.conf
# command=/home/whodis/whodis/venv/bin/gunicorn ...

sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start whodis
```

---

### Issue: 502 Bad Gateway from nginx

**Symptoms:** Nginx shows 502 error, application appears down

**Diagnosis:**
```bash
# Check application is running
sudo supervisorctl status whodis

# Check unix socket exists
ls -la /home/whodis/whodis/whodis.sock

# Check nginx error log
sudo tail -50 /var/log/nginx/whodis.error.log
```

**Solution:**
```bash
# Restart application
sudo supervisorctl restart whodis

# Check socket permissions
sudo chmod 666 /home/whodis/whodis/whodis.sock

# Verify nginx config
sudo nginx -t
sudo systemctl reload nginx

# If socket doesn't exist, check gunicorn bind address
# In supervisor config: --bind unix:/home/whodis/whodis/whodis.sock
```

---

### Issue: SSL certificate errors

**Symptoms:** Browser shows "Your connection is not private" warning

**Solution:**
```bash
# Check certificate expiration
openssl x509 -in /etc/ssl/certs/whodis.example.com.crt -noout -dates

# Renew Let's Encrypt certificate
sudo certbot renew

# Or manually install certificate
sudo cp whodis.crt /etc/ssl/certs/whodis.example.com.crt
sudo cp whodis.key /etc/ssl/private/whodis.example.com.key
sudo chmod 600 /etc/ssl/private/whodis.example.com.key

# Reload nginx
sudo systemctl reload nginx
```

## Getting Additional Help

### Collect Diagnostic Information

Before requesting support, collect:

```bash
# System information
uname -a > diagnostics.txt
python --version >> diagnostics.txt
psql --version >> diagnostics.txt

# Application status
sudo supervisorctl status >> diagnostics.txt
sudo systemctl status nginx >> diagnostics.txt
sudo systemctl status postgresql >> diagnostics.txt

# Recent errors
echo "=== Application Errors ===" >> diagnostics.txt
sudo tail -100 /var/log/whodis/error.log >> diagnostics.txt

echo "=== Nginx Errors ===" >> diagnostics.txt
sudo tail -100 /var/log/nginx/whodis.error.log >> diagnostics.txt

echo "=== Recent Audit Logs ===" >> diagnostics.txt
psql -U whodis_user -d whodis_db -c "SELECT * FROM error_log ORDER BY timestamp DESC LIMIT 20;" >> diagnostics.txt

# Review diagnostics.txt before sharing (remove sensitive data!)
```

### Support Resources

- **Documentation**: [docs/](.) directory
- **Architecture**: [docs/architecture.md](architecture.md)
- **Database**: [docs/database.md](database.md)
- **Deployment**: [docs/deployment.md](deployment.md)
- **Security**: [SECURITY.md](../SECURITY.md)
- **GitHub Issues**: https://github.com/jslitzkerttcu/Who-Dis/issues
- **Security Reports**: See [SECURITY.md](../SECURITY.md)

---

*Last Updated: December 29, 2025*
