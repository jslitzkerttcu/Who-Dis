# Admin Tasks Guide

This guide covers administrative tasks for WhoDis administrators (users with "admin" role).

## Table of Contents
- [Accessing the Admin Panel](#accessing-the-admin-panel)
- [User Management](#user-management)
- [Configuration Management](#configuration-management)
- [Cache and Token Management](#cache-and-token-management)
- [Audit Log Review](#audit-log-review)
- [Job Role Compliance](#job-role-compliance)
- [Blocked Numbers Management](#blocked-numbers-management)
- [System Maintenance](#system-maintenance)
- [Troubleshooting](#troubleshooting)

## Accessing the Admin Panel

### Prerequisites
- **Admin role** assigned to your account
- Active Azure AD login session
- Network access to WhoDis server

### Navigation
1. Log in to WhoDis with your Azure AD credentials
2. Click the **user dropdown** in the top right corner
3. Select **Admin** from the dropdown menu
4. You'll be redirected to the Admin Dashboard

**URL**: `https://your-whodis-url/admin`

### Admin Dashboard Overview

The dashboard displays several cards with system information:

```
┌─────────────────────────────────────────────────────────┐
│ API Tokens                      Cache Management        │
│ - Microsoft Graph status        - Search cache stats   │
│ - Genesys Cloud status          - Genesys cache stats  │
│ - Token expiration times        - Refresh controls     │
│                                                         │
│ User Management                 Configuration          │
│ - Total users                   - Edit settings        │
│ - Users by role                 - View encrypted keys  │
│ - Add/Edit users                                       │
│                                                         │
│ Audit Logs                      Job Role Compliance    │
│ - Recent activity               - Mapping management   │
│ - Search logs                   - Compliance reports   │
│ - Filter and export                                    │
└─────────────────────────────────────────────────────────┘
```

## User Management

### Viewing Users

1. Navigate to **Admin** → **Users**
2. View the **users table** with columns:
   - Email address
   - Role (Admin, Editor, Viewer)
   - Created date
   - Last updated date
   - Actions (Edit, Delete)

**Features:**
- **Search**: Filter users by email
- **Sort**: Click column headers to sort
- **Pagination**: Navigate through pages if many users

### Adding a New User

1. Click **Add User** button
2. Fill in the form:
   - **Email**: User's corporate email (must match Azure AD)
   - **Role**: Select Admin, Editor, or Viewer
3. Click **Save**

**Important Notes:**
- Email must match the user's Azure AD login email exactly
- User will automatically be granted access on next login
- New users inherit default session timeout settings
- Role determines which features the user can access

**Role Capabilities:**

| Feature | Viewer | Editor | Admin |
|---------|--------|--------|-------|
| Search users | ✓ | ✓ | ✓ |
| View results | ✓ | ✓ | ✓ |
| Edit blocked numbers | ✗ | ✓ | ✓ |
| Manage users | ✗ | ✗ | ✓ |
| View audit logs | ✗ | ✗ | ✓ |
| Edit configuration | ✗ | ✗ | ✓ |
| Manage cache/tokens | ✗ | ✗ | ✓ |
| Job role compliance | ✗ | ✗ | ✓ |

### Editing a User

1. Click **Edit** next to the user
2. Modify the **role** (cannot change email)
3. Click **Save**

**Use Cases:**
- Promote a viewer to editor for help desk access
- Demote an editor to viewer when leaving help desk
- Grant admin access to new system administrator

### Deleting a User

1. Click **Delete** next to the user
2. Confirm the deletion

**Warning:**
- This action is **permanent**
- User will lose access immediately
- Audit logs show deletion with admin email and IP
- Cannot delete your own account while logged in

## Configuration Management

### Viewing Configuration

1. Navigate to **Admin** → **Configuration**
2. View configuration grouped by category:
   - **auth**: Authentication settings
   - **flask**: Flask application settings
   - **ldap**: Active Directory/LDAP settings
   - **genesys**: Genesys Cloud API settings
   - **graph**: Microsoft Graph API settings
   - **search**: Search behavior settings
   - **session**: Session timeout settings

### Understanding Configuration Display

**Encrypted Values:**
- Shown as: `[encrypted value]`
- Cannot be viewed in plaintext for security
- Examples: `SECRET_KEY`, `LDAP_BIND_PASSWORD`, client secrets

**Plaintext Values:**
- Displayed directly
- Examples: `LDAP_HOST`, `SESSION_TIMEOUT`, `SEARCH_CACHE_TTL`

**Configuration Format:**
```
Category: auth
├── SECRET_KEY: [encrypted value]
├── ADMIN_FALLBACK_EMAIL: [encrypted value]
└── ADMIN_FALLBACK_PASSWORD: [encrypted value]

Category: ldap
├── LDAP_HOST: ldap.example.com
├── LDAP_PORT: 636
├── LDAP_USE_SSL: true
└── LDAP_BIND_PASSWORD: [encrypted value]
```

### Editing Configuration

**Method 1: Web Interface (Recommended)**

1. Navigate to **Admin** → **Configuration**
2. Click **Edit Configuration**
3. Modify values in the form:
   - Enter new plaintext value (will be encrypted if needed)
   - Leave encrypted fields blank to keep current value
4. Click **Save Changes**

**Important:**
- Changes take effect **immediately** (no restart required)
- Encrypted values are re-encrypted on save
- Configuration history tracked in audit log
- Invalid values may break functionality

**Method 2: Database Direct Edit (Advanced)**

Only for experienced administrators:

```bash
# Access PostgreSQL
psql -U whodis_user -d whodis_db -h localhost

# View configuration
SELECT category, key, value FROM configuration ORDER BY category, key;

# Update a value (encrypts automatically if needed)
# Use Python script instead - direct SQL edit bypasses encryption
```

**Recommended:** Use web interface or `scripts/export_config.py` for safety.

### Common Configuration Changes

#### Change Session Timeout

1. Navigate to **Admin** → **Configuration**
2. Find **session** → **SESSION_TIMEOUT**
3. Change value (in seconds):
   - Default: `900` (15 minutes)
   - Shorter: `600` (10 minutes)
   - Longer: `1800` (30 minutes)
4. Save changes

**Effect:** All new sessions use new timeout; existing sessions unaffected until refresh.

#### Update LDAP Credentials

1. Navigate to **Admin** → **Configuration**
2. Find **ldap** → **LDAP_BIND_PASSWORD**
3. Enter new password
4. Save changes

**Testing:**
- Perform a test search
- Check audit logs for LDAP errors
- If errors, revert to previous password

#### Update API Credentials

**Genesys Cloud:**
1. Navigate to **Admin** → **Configuration**
2. Update:
   - `GENESYS_CLIENT_ID`
   - `GENESYS_CLIENT_SECRET`
3. Save changes
4. Navigate to **Admin** → **Cache** → **Refresh Tokens**

**Microsoft Graph:**
1. Navigate to **Admin** → **Configuration**
2. Update:
   - `GRAPH_CLIENT_ID`
   - `GRAPH_CLIENT_SECRET`
3. Save changes
4. Refresh tokens

#### Enable/Disable Search Services

1. Navigate to **Admin** → **Configuration**
2. Find **search** category
3. Set to `true` or `false`:
   - `SEARCH_LDAP_ENABLED`
   - `SEARCH_GENESYS_ENABLED`
   - `SEARCH_GRAPH_ENABLED`
4. Save changes

**Use Case:** Temporarily disable a service if API is down.

## Cache and Token Management

### API Token Status

The **API Tokens** card shows:
- **Microsoft Graph**: Token status and expiration
- **Genesys Cloud**: Token status and expiration

**Status Indicators:**
- **Green "Valid"**: Token is active and unexpired
- **Yellow "Expires Soon"**: Token expires in < 1 hour
- **Red "Expired"**: Token has expired, refresh needed
- **Gray "No Token"**: No token in database

**Hover** over status to see exact expiration time.

### Refreshing API Tokens

**Automatic Refresh:**
- Background service checks tokens every 5 minutes
- Auto-refreshes tokens expiring within 10 minutes
- No admin action needed

**Manual Refresh:**
1. Navigate to **Admin** → **Cache**
2. Click **Refresh All Tokens**
3. Wait for confirmation message

**When to Refresh Manually:**
- After updating API credentials
- Token shows as expired
- Search returns authentication errors
- Troubleshooting API issues

### Search Cache Management

**View Cache Statistics:**

The **Cache Management** card shows:
- Total cached searches
- Cache hit rate
- Cache size (estimated)
- Last refresh time

**Clear Search Cache:**

1. Navigate to **Admin** → **Cache**
2. Click **Clear Search Cache**
3. Confirm action

**Use Cases:**
- Force fresh data after backend changes
- Troubleshooting stale data issues
- After major Active Directory changes
- Testing search behavior

**Note:** Cleared cache rebuilds automatically on next search.

### Genesys Cache Management

**Genesys Data Cached:**
- Groups
- Skills
- Locations

**View Genesys Cache:**

Statistics show:
- Number of groups cached
- Number of skills cached
- Number of locations cached
- Last cache refresh time

**Refresh Genesys Cache:**

1. Navigate to **Admin** → **Cache**
2. Click **Refresh Genesys Cache**
3. Wait for completion (may take 10-30 seconds)

**Automatic Refresh:** Every 6 hours

**When to Refresh Manually:**
- New Genesys groups created
- Skills added/updated
- Location changes
- Search shows outdated Genesys data

## Audit Log Review

### Accessing Audit Logs

1. Navigate to **Admin** → **Audit Logs**
2. View recent activity in the logs table

### Understanding Log Entries

**Columns:**
- **Timestamp**: When event occurred (with timezone)
- **Event Type**: Category of event
- **User Email**: Who performed the action
- **IP Address**: Source IP of request
- **Details**: Event-specific information

**Event Types:**

| Type | Description | Example |
|------|-------------|---------|
| `search` | User searched for someone | Query: "john.doe", Results: 1 |
| `access` | Access denied event | User denied access to admin panel |
| `admin` | User management action | Added user: editor@example.com |
| `config` | Configuration change | Updated SESSION_TIMEOUT: 900 → 1800 |
| `error` | Application error | LDAP timeout on search |

**Color Coding:**
- **Blue**: Search events
- **Yellow**: Access/authentication events
- **Green**: Admin actions
- **Purple**: Configuration changes
- **Red**: Errors

### Filtering Audit Logs

**Date Range:**
1. Select **Start Date** and **End Date**
2. Click **Filter**

**By User:**
1. Enter email in **User Email** field
2. Click **Filter**

**By Event Type:**
1. Select type from **Event Type** dropdown
2. Click **Filter**

**By Search Query:**
1. Enter search term in **Search Query** field
2. Click **Filter**
3. Shows all searches for that term

**Combine Filters:**
- All filters work together (AND logic)
- Clear filters: Click **Reset**

### Viewing Log Details

1. Click on any log entry row
2. View expanded details in modal:
   - Full event data (JSON format)
   - Session ID
   - User agent (browser)
   - Additional metadata

**Use Cases:**
- Investigate suspicious activity
- Track down who changed configuration
- Review search patterns
- Troubleshoot errors

### Exporting Audit Logs

1. Apply desired filters
2. Click **Export to CSV**
3. Save file to your computer

**CSV Contains:**
- All filtered log entries
- All columns including details
- Suitable for Excel or data analysis

**Use Cases:**
- Compliance reporting
- Security audits
- Historical analysis
- Backup records

## Job Role Compliance

**Note:** This feature may not be enabled on all installations. Contact your system administrator if you don't see this option.

### Accessing Compliance Matrix

1. Navigate to **Admin** → **Job Role Compliance**
2. View the compliance dashboard

### Understanding the Matrix

The compliance matrix shows:
- **Job Codes**: From HR system (Keystone)
- **System Roles**: From Genesys Cloud
- **Mappings**: Which job codes should have which system roles

**Purpose:** Ensure employees have correct system access based on their job.

### Managing Job Codes

**View Job Codes:**
- Table shows all job codes from HR system
- Columns: Code, Description, Mapping Count

**Job Code Details:**
1. Click on a job code
2. View:
   - Code and description
   - Expected system roles
   - Employees with this job code
   - Compliance status

### Managing System Roles

**View System Roles:**
- Table shows all roles from Genesys Cloud
- Columns: Role Name, Mapping Count

**System Role Details:**
1. Click on a system role
2. View:
   - Role name and description
   - Job codes that should have this role
   - Employees with this role

### Creating Mappings

1. Navigate to **Mappings** tab
2. Click **Add Mapping**
3. Select:
   - **Job Code**: From dropdown
   - **System Role**: From dropdown
4. Click **Save**

**Example:**
- Job Code: "CSR" (Customer Service Representative)
- System Role: "Customer Service Agent"

**Effect:** All employees with job code "CSR" should have "Customer Service Agent" role in Genesys.

### Viewing Compliance Reports

1. Navigate to **Compliance** tab
2. View compliance status:
   - **Compliant**: Employee has expected roles
   - **Missing Roles**: Employee lacks expected roles
   - **Extra Roles**: Employee has unexpected roles

**Filter Options:**
- By job code
- By compliance status
- By department

**Export:**
- Click **Export Report**
- Save CSV for review or action

### Compliance Workflow

**Typical Process:**
1. HR creates new job code in Keystone
2. Admin creates mapping in WhoDis (Job Code → System Roles)
3. Run compliance report
4. Identify employees out of compliance
5. Update Genesys roles to match expected mappings
6. Re-run compliance report to verify

## Blocked Numbers Management

**Note:** This feature requires "editor" or "admin" role.

### Accessing Blocked Numbers

1. Navigate to **Utilities** → **Blocked Numbers**
2. View the blocked numbers table

### Understanding Blocked Numbers

**Purpose:** Prevent Genesys from routing calls from specific phone numbers.

**Use Cases:**
- Block spam/robocall numbers
- Block abusive callers
- Block known fraud numbers
- Block internal test numbers

### Adding Blocked Numbers

1. Click **Add Blocked Number**
2. Fill in the form:
   - **Phone Number**: Enter number in any format
   - **Reason**: Why this number is blocked
   - **Blocked By**: Your email (auto-filled)
3. Click **Save**

**Phone Number Formats Accepted:**
```
918-749-1234
(918) 749-1234
9187491234
+19187491234
1-918-749-1234
```

**System Normalizes To:**
```
+19187491234
```

### Viewing Blocked Numbers

**Table Columns:**
- **Phone Number**: Normalized format
- **Reason**: Why blocked
- **Blocked By**: Admin who added it
- **Blocked Date**: When added
- **Actions**: Edit, Delete

**Search:**
- Enter phone number or partial number
- Click **Search**

### Editing Blocked Numbers

1. Click **Edit** next to the number
2. Modify the reason (cannot change number)
3. Click **Save**

**Audit:** Edit is logged with admin email and timestamp.

### Removing Blocked Numbers

1. Click **Delete** next to the number
2. Confirm removal

**When to Remove:**
- Number no longer a threat
- Accidental block
- Testing purposes

**Audit:** Deletion is logged with admin email and IP.

### Syncing with Genesys

**Automatic Sync:**
- Blocked numbers sync to Genesys every 15 minutes
- No manual action needed

**Manual Sync:**
1. Click **Sync Now** button
2. Wait for confirmation

**When to Manual Sync:**
- Urgent block needed immediately
- Testing block functionality
- After bulk changes

**Sync Status:**
- Green: Last sync successful
- Yellow: Sync in progress
- Red: Last sync failed (check logs)

## System Maintenance

### Regular Maintenance Tasks

**Weekly:**
- [ ] Review audit logs for unusual activity
- [ ] Check API token status
- [ ] Review error logs for patterns

**Monthly:**
- [ ] Export audit logs for compliance
- [ ] Review user list for inactive accounts
- [ ] Check cache performance statistics
- [ ] Run compliance reports (if enabled)

**Quarterly:**
- [ ] Review and update configuration
- [ ] Test disaster recovery procedures
- [ ] Review blocked numbers list
- [ ] Audit user roles for accuracy

**Annually:**
- [ ] Rotate API credentials
- [ ] Review security settings
- [ ] Update documentation
- [ ] Performance tuning review

### Backup Procedures

**Configuration Backup:**

```bash
# Export configuration to encrypted file
python scripts/export_config.py

# Output: config_backup_YYYYMMDD_HHMMSS.json
# Store securely - contains encrypted secrets
```

**Database Backup:**

```bash
# PostgreSQL backup
pg_dump -U whodis_user -h localhost whodis_db > whodis_backup_$(date +%Y%m%d).sql

# Compress backup
gzip whodis_backup_$(date +%Y%m%d).sql

# Store offsite or in secure location
```

**Frequency:** Daily automated backups recommended.

### Monitoring

**Key Metrics to Monitor:**
- API token expiration times
- Search cache hit rate
- Error rate in audit logs
- Session timeout rate
- Database connection pool usage

**Alerting:**
- Set up alerts for expired API tokens
- Monitor error log for repeated failures
- Alert on failed Genesys cache refreshes
- Track unusual access patterns

**Tools:**
- Application logs: `logs/whodis.log`
- PostgreSQL logs: System-dependent
- Azure App Service logs: Azure Portal
- Custom monitoring: Integrate with your tools

### Performance Tuning

**Slow Searches:**
1. Check LDAP timeout settings
2. Review PostgreSQL query performance
3. Analyze cache hit rates
4. Consider increasing cache TTL

**High Database Load:**
1. Review audit log retention settings
2. Check connection pool size
3. Optimize slow queries
4. Consider database scaling

**Memory Usage:**
1. Monitor cache sizes
2. Review session cleanup
3. Check for memory leaks in logs
4. Restart application periodically

## Troubleshooting

### Common Admin Tasks Issues

**Cannot Access Admin Panel**

**Symptoms:** "Access Denied" when navigating to /admin

**Solutions:**
1. Verify your user account has "admin" role:
   ```sql
   SELECT email, role FROM users WHERE email = 'your.email@example.com';
   ```
2. Check if Azure AD authentication is working
3. Clear browser cache and cookies
4. Review access_attempts table for denials

**Configuration Changes Not Taking Effect**

**Symptoms:** Changed config but behavior unchanged

**Solutions:**
1. Verify changes saved (check configuration table)
2. Check for typos in configuration keys
3. Review error logs for configuration errors
4. Some changes may require cache clear
5. Restart application if using old version

**API Tokens Keep Expiring**

**Symptoms:** Tokens expire despite refresh attempts

**Solutions:**
1. Check API credentials are correct
2. Verify client ID and secret in configuration
3. Test credentials manually via API
4. Review token refresh service logs
5. Check network connectivity to API endpoints

**Search Cache Not Clearing**

**Symptoms:** Old data persists after cache clear

**Solutions:**
1. Check browser cache (hard refresh: Ctrl+Shift+R)
2. Verify cache TTL settings
3. Check search_cache table directly
4. Review cache cleanup logs
5. Clear PostgreSQL query cache

**Audit Logs Missing Entries**

**Symptoms:** Expected events not appearing in logs

**Solutions:**
1. Check audit log retention settings
2. Verify PostgreSQL connection
3. Review audit service configuration
4. Check for audit log cleanup jobs
5. Verify log level settings

**Job Role Compliance Not Updating**

**Symptoms:** Compliance data stale or incorrect

**Solutions:**
1. Refresh employee profiles:
   ```bash
   python scripts/refresh_employee_profiles.py refresh
   ```
2. Check data warehouse connectivity
3. Verify Keystone API access
4. Review employee_profiles table
5. Check mapping definitions

### Getting Help

**Internal Resources:**
- **[Troubleshooting Guide](../troubleshooting.md)**: Comprehensive troubleshooting
- **[Architecture Docs](../architecture.md)**: System design details
- **[Database Docs](../database.md)**: Database schema and queries

**Support Contacts:**
- **Technical Issues**: IT Help Desk
- **Security Issues**: See [SECURITY.md](../../SECURITY.md)
- **Feature Requests**: GitHub Issues

**Diagnostic Scripts:**

```bash
# Check overall system status
python scripts/check_config_status.py

# Verify deployment health
python scripts/verify_deployment.py

# Diagnose configuration issues
python scripts/diagnose_config.py

# Test Genesys cache
python scripts/check_genesys_cache.py
```

---

*Last Updated: December 29, 2025*
