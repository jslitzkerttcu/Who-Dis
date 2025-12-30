# WhoDis Production Deployment Guide

This guide provides comprehensive instructions for deploying WhoDis to production environments.

## Table of Contents
- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Infrastructure Requirements](#infrastructure-requirements)
- [Deployment Options](#deployment-options)
- [Database Setup](#database-setup)
- [Application Configuration](#application-configuration)
- [Reverse Proxy Setup](#reverse-proxy-setup)
- [Security Hardening](#security-hardening)
- [Monitoring and Logging](#monitoring-and-logging)
- [Backup and Disaster Recovery](#backup-and-disaster-recovery)
- [Post-Deployment Verification](#post-deployment-verification)
- [Troubleshooting](#troubleshooting)

## Pre-Deployment Checklist

Before deploying to production, ensure you have:

### Required Information
- [ ] PostgreSQL server details (host, port, credentials)
- [ ] Azure AD tenant ID and application registration
- [ ] LDAP/Active Directory connection details
- [ ] Genesys Cloud API credentials (client ID, secret, org ID)
- [ ] Microsoft Graph API credentials (tenant ID, client ID, secret)
- [ ] Data warehouse connection details (if using job role compliance)
- [ ] SSL certificate for HTTPS (or reverse proxy SSL termination)
- [ ] Domain name and DNS configuration

### Security Preparation
- [ ] Generate strong `WHODIS_ENCRYPTION_KEY` (backup securely!)
- [ ] Create strong PostgreSQL passwords (20+ characters)
- [ ] Review and update security headers configuration
- [ ] Plan firewall rules and network security groups
- [ ] Prepare backup encryption keys (if encrypting backups)

### Documentation Review
- [ ] Read [SECURITY.md](../SECURITY.md) - Security best practices
- [ ] Review [docs/database.md](database.md) - Database management
- [ ] Check [docs/architecture.md](architecture.md) - System architecture
- [ ] Review [CHANGELOG.md](../CHANGELOG.md) - Recent changes

## Infrastructure Requirements

### Minimum Requirements

**Application Server:**
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disk**: 20 GB (plus space for logs and cache)
- **OS**: Ubuntu 20.04+ LTS or Windows Server 2019+

**Database Server:**
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disk**: 50 GB SSD (or more based on audit log retention)
- **PostgreSQL**: Version 12 or higher

**Network:**
- **Inbound**: HTTPS (443) from users, optionally HTTP (80) for redirect
- **Outbound**: Access to Azure AD, LDAP server, Genesys Cloud, Microsoft Graph
- **Internal**: PostgreSQL port (5432) from application server
- **Bandwidth**: Depends on user count (recommend 10+ Mbps for small deployments)

### Recommended for Production

**Application Server:**
- **CPU**: 4+ cores
- **RAM**: 8 GB
- **Disk**: 100 GB SSD
- **Redundancy**: Load-balanced multiple instances

**Database Server:**
- **CPU**: 4+ cores
- **RAM**: 8+ GB
- **Disk**: 200+ GB SSD with RAID
- **High Availability**: PostgreSQL replication or Azure Database for PostgreSQL

## Deployment Options

### Option 1: Azure App Service (Recommended for Azure Environments)

**Advantages:**
- Managed infrastructure
- Auto-scaling capabilities
- Built-in SSL/TLS
- Azure AD integration via Easy Auth
- Automated backups

**Deployment Steps:**

1. **Create Azure App Service**
   ```bash
   az webapp create \
     --name whodis-prod \
     --resource-group whodis-rg \
     --plan whodis-plan \
     --runtime "PYTHON:3.10"
   ```

2. **Configure Application Settings**
   ```bash
   az webapp config appsettings set \
     --name whodis-prod \
     --resource-group whodis-rg \
     --settings \
       POSTGRES_HOST="whodis-db.postgres.database.azure.com" \
       POSTGRES_PORT="5432" \
       POSTGRES_DB="whodis_db" \
       POSTGRES_USER="whodis_user@whodis-db" \
       POSTGRES_PASSWORD="your-secure-password" \
       WHODIS_ENCRYPTION_KEY="your-encryption-key"
   ```

3. **Enable Azure AD Authentication**
   - In Azure Portal, go to App Service → Authentication
   - Add identity provider → Microsoft
   - Configure app registration
   - Enable "Require authentication"

4. **Deploy Code**
   ```bash
   # Using Git deployment
   git remote add azure https://whodis-prod.scm.azurewebsites.net/whodis-prod.git
   git push azure main

   # Or using Azure CLI
   az webapp deploy --name whodis-prod --resource-group whodis-rg --src-path ./
   ```

5. **Configure Startup Command**
   ```bash
   az webapp config set \
     --name whodis-prod \
     --resource-group whodis-rg \
     --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 run:app"
   ```

### Option 2: Traditional Linux Server (Ubuntu)

**Advantages:**
- Full control over infrastructure
- Cost-effective for on-premises
- Flexible configuration

**Deployment Steps:**

1. **Prepare Server**
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y

   # Install dependencies
   sudo apt install -y python3.10 python3.10-venv python3-pip postgresql-client nginx supervisor git
   ```

2. **Create Application User**
   ```bash
   sudo useradd -m -s /bin/bash whodis
   sudo usermod -aG www-data whodis
   ```

3. **Deploy Application**
   ```bash
   # Switch to whodis user
   sudo su - whodis

   # Clone repository
   git clone https://github.com/jslitzkerttcu/Who-Dis.git /home/whodis/whodis
   cd /home/whodis/whodis

   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   pip install gunicorn  # Production WSGI server

   # Create .env file
   cat > .env << EOF
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=whodis_db
   POSTGRES_USER=whodis_user
   POSTGRES_PASSWORD=your-secure-password
   WHODIS_ENCRYPTION_KEY=your-encryption-key
   EOF

   chmod 600 .env
   ```

4. **Configure Supervisor for Process Management**
   ```bash
   # Exit whodis user
   exit

   # Create supervisor config
   sudo nano /etc/supervisor/conf.d/whodis.conf
   ```

   Add:
   ```ini
   [program:whodis]
   command=/home/whodis/whodis/venv/bin/gunicorn --workers 4 --bind unix:/home/whodis/whodis/whodis.sock --timeout 600 run:app
   directory=/home/whodis/whodis
   user=whodis
   autostart=true
   autorestart=true
   stderr_logfile=/var/log/whodis/error.log
   stdout_logfile=/var/log/whodis/access.log
   environment=PATH="/home/whodis/whodis/venv/bin"
   ```

   ```bash
   # Create log directory
   sudo mkdir -p /var/log/whodis
   sudo chown whodis:whodis /var/log/whodis

   # Start service
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl start whodis
   ```

### Option 3: Docker Deployment

**Advantages:**
- Consistent environments
- Easy scaling with orchestration
- Simplified dependency management

**Note:** Docker support not yet implemented. If needed, create:
- `Dockerfile` for application
- `docker-compose.yml` for multi-container setup
- Environment variable configuration
- Volume mounts for persistent data

## Database Setup

### PostgreSQL Installation and Configuration

#### On Ubuntu Server

1. **Install PostgreSQL**
   ```bash
   sudo apt install -y postgresql postgresql-contrib
   ```

2. **Configure PostgreSQL**
   ```bash
   sudo nano /etc/postgresql/12/main/postgresql.conf
   ```

   Recommended production settings:
   ```ini
   # Connection settings
   listen_addresses = 'localhost'  # Or specific IP for remote app server
   max_connections = 100

   # Memory settings (adjust based on available RAM)
   shared_buffers = 256MB
   effective_cache_size = 1GB
   maintenance_work_mem = 64MB
   work_mem = 4MB

   # Performance
   random_page_cost = 1.1  # For SSD
   effective_io_concurrency = 200

   # Logging
   log_destination = 'stderr'
   logging_collector = on
   log_directory = 'log'
   log_filename = 'postgresql-%Y-%m-%d.log'
   log_rotation_age = 1d
   log_min_duration_statement = 1000  # Log slow queries (1+ second)
   ```

3. **Configure Authentication**
   ```bash
   sudo nano /etc/postgresql/12/main/pg_hba.conf
   ```

   Add (replace with actual app server IP if remote):
   ```
   # WhoDis application access
   host    whodis_db    whodis_user    127.0.0.1/32    md5
   ```

4. **Create Database and User**
   ```bash
   sudo -u postgres psql
   ```

   ```sql
   CREATE DATABASE whodis_db;
   CREATE USER whodis_user WITH PASSWORD 'your-secure-password-min-20-chars';
   GRANT ALL PRIVILEGES ON DATABASE whodis_db TO whodis_user;
   \q
   ```

5. **Create Tables**
   ```bash
   psql -U whodis_user -d whodis_db -h localhost -f /home/whodis/whodis/database/create_tables.sql
   ```

6. **Analyze Tables**
   ```bash
   psql -U postgres -d whodis_db -h localhost -f /home/whodis/whodis/database/analyze_tables.sql
   ```

#### Azure Database for PostgreSQL

1. **Create Azure PostgreSQL Server**
   ```bash
   az postgres server create \
     --resource-group whodis-rg \
     --name whodis-db \
     --location eastus \
     --admin-user whodis_admin \
     --admin-password "your-secure-password" \
     --sku-name GP_Gen5_2 \
     --version 12
   ```

2. **Configure Firewall**
   ```bash
   # Allow Azure services
   az postgres server firewall-rule create \
     --resource-group whodis-rg \
     --server whodis-db \
     --name AllowAzureServices \
     --start-ip-address 0.0.0.0 \
     --end-ip-address 0.0.0.0

   # Allow app server (if external)
   az postgres server firewall-rule create \
     --resource-group whodis-rg \
     --server whodis-db \
     --name AllowAppServer \
     --start-ip-address <app-server-ip> \
     --end-ip-address <app-server-ip>
   ```

3. **Create Database**
   ```bash
   psql -h whodis-db.postgres.database.azure.com -U whodis_admin@whodis-db postgres
   ```

   ```sql
   CREATE DATABASE whodis_db;
   CREATE USER whodis_user WITH PASSWORD 'your-secure-password';
   GRANT ALL PRIVILEGES ON DATABASE whodis_db TO whodis_user;
   ```

4. **Run Migrations**
   ```bash
   psql -h whodis-db.postgres.database.azure.com -U whodis_user@whodis-db -d whodis_db -f database/create_tables.sql
   ```

### Database Performance Tuning

**Indexes** (already created by schema):
- Audit logs indexed on timestamp, user_email, event_type
- Job role mappings indexed on job_code_id, system_role_id
- Sessions indexed on user_email, expires_at
- API tokens indexed on service_name, expires_at

**Maintenance Tasks:**

```bash
# Weekly vacuum and analyze
psql -U whodis_user -d whodis_db -c "VACUUM ANALYZE;"

# Monthly full vacuum (requires downtime)
psql -U whodis_user -d whodis_db -c "VACUUM FULL;"

# Check database size
psql -U whodis_user -d whodis_db -c "SELECT pg_size_pretty(pg_database_size('whodis_db'));"
```

## Application Configuration

### Environment Variables

**Required Variables:**
```bash
# Database connection (cannot be in database config - bootstrap problem)
POSTGRES_HOST=whodis-db.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DB=whodis_db
POSTGRES_USER=whodis_user@whodis-db
POSTGRES_PASSWORD=your-very-secure-password-20plus-characters

# Encryption key (CRITICAL - back this up securely!)
WHODIS_ENCRYPTION_KEY=your-fernet-encryption-key-generated-and-backed-up
```

**Generate Encryption Key:**
```python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**⚠️ CRITICAL:** Store `WHODIS_ENCRYPTION_KEY` securely:
- Use Azure Key Vault, AWS Secrets Manager, or similar
- Keep offline backup in secure location
- Document key rotation procedures
- Changing this key makes all encrypted data unreadable!

### Encrypted Configuration (via Admin UI or Script)

After initial deployment, configure via admin interface (`/admin/configuration`) or scripts:

**Flask Configuration:**
```python
config_set("flask", "secret_key", "your-unique-secret-key-for-sessions")
config_set("flask", "debug", "false")
config_set("flask", "session_cookie_secure", "true")
config_set("flask", "session_cookie_httponly", "true")
config_set("flask", "session_cookie_samesite", "Lax")
```

**LDAP/Active Directory:**
```python
config_set("ldap", "server", "ldaps://dc.example.com:636")
config_set("ldap", "bind_dn", "CN=WhoDis Service,OU=Service Accounts,DC=example,DC=com")
config_set("ldap", "bind_password", "service-account-password")
config_set("ldap", "base_dn", "DC=example,DC=com")
config_set("ldap", "use_ssl", "true")
```

**Genesys Cloud:**
```python
config_set("genesys", "client_id", "your-genesys-client-id")
config_set("genesys", "client_secret", "your-genesys-client-secret")
config_set("genesys", "org_id", "your-genesys-org-id")
config_set("genesys", "region", "us-east-1")
```

**Microsoft Graph:**
```python
config_set("graph", "tenant_id", "your-azure-tenant-id")
config_set("graph", "client_id", "your-graph-app-client-id")
config_set("graph", "client_secret", "your-graph-app-client-secret")
```

**Session Configuration:**
```python
config_set("session", "timeout_minutes", "15")
config_set("session", "warning_minutes", "2")
config_set("session", "extend_on_activity", "true")
```

### Verify Configuration

```bash
# Check configuration status
python scripts/check_config_status.py

# Verify encryption
python scripts/verify_encrypted_config.py

# Test connections
python scripts/diagnose_config.py
```

## Reverse Proxy Setup

### Nginx Configuration

1. **Install Nginx**
   ```bash
   sudo apt install -y nginx
   ```

2. **Create Site Configuration**
   ```bash
   sudo nano /etc/nginx/sites-available/whodis
   ```

   ```nginx
   # Rate limiting zone
   limit_req_zone $binary_remote_addr zone=whodis_limit:10m rate=10r/s;

   # Upstream application
   upstream whodis_app {
       server unix:/home/whodis/whodis/whodis.sock fail_timeout=0;
   }

   # HTTP to HTTPS redirect
   server {
       listen 80;
       server_name whodis.example.com;
       return 301 https://$server_name$request_uri;
   }

   # HTTPS server
   server {
       listen 443 ssl http2;
       server_name whodis.example.com;

       # SSL configuration
       ssl_certificate /etc/ssl/certs/whodis.example.com.crt;
       ssl_certificate_key /etc/ssl/private/whodis.example.com.key;
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers HIGH:!aNULL:!MD5;
       ssl_prefer_server_ciphers on;
       ssl_session_cache shared:SSL:10m;
       ssl_session_timeout 10m;

       # Security headers
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
       add_header X-Frame-Options "SAMEORIGIN" always;
       add_header X-Content-Type-Options "nosniff" always;
       add_header X-XSS-Protection "1; mode=block" always;
       add_header Referrer-Policy "strict-origin-when-cross-origin" always;
       add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdnjs.cloudflare.com; img-src 'self' data: https:;" always;

       # Logging
       access_log /var/log/nginx/whodis.access.log;
       error_log /var/log/nginx/whodis.error.log;

       # Max upload size
       client_max_body_size 10M;

       # Rate limiting
       limit_req zone=whodis_limit burst=20 nodelay;

       # Proxy settings
       location / {
           proxy_pass http://whodis_app;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;

           # Azure AD SSO headers (if using Easy Auth)
           proxy_set_header X-MS-CLIENT-PRINCIPAL-NAME $http_x_ms_client_principal_name;
           proxy_set_header X-MS-CLIENT-PRINCIPAL-ID $http_x_ms_client_principal_id;

           # Timeouts
           proxy_connect_timeout 60s;
           proxy_send_timeout 60s;
           proxy_read_timeout 60s;

           # Buffering
           proxy_buffering on;
           proxy_buffer_size 4k;
           proxy_buffers 8 4k;
       }

       # Static files (if serving directly)
       location /static {
           alias /home/whodis/whodis/app/static;
           expires 1y;
           add_header Cache-Control "public, immutable";
       }
   }
   ```

3. **Enable Site**
   ```bash
   sudo ln -s /etc/nginx/sites-available/whodis /etc/nginx/sites-enabled/
   sudo nginx -t  # Test configuration
   sudo systemctl reload nginx
   ```

### Apache Configuration (Alternative)

```apache
<VirtualHost *:80>
    ServerName whodis.example.com
    Redirect permanent / https://whodis.example.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName whodis.example.com

    SSLEngine on
    SSLCertificateFile /etc/ssl/certs/whodis.example.com.crt
    SSLCertificateKeyFile /etc/ssl/private/whodis.example.com.key
    SSLProtocol all -SSLv2 -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite HIGH:!aNULL:!MD5

    # Security headers
    Header always set Strict-Transport-Security "max-age=31536000"
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"

    # Proxy settings
    ProxyPreserveHost On
    ProxyPass / unix:/home/whodis/whodis/whodis.sock|http://whodis-app/
    ProxyPassReverse / unix:/home/whodis/whodis/whodis.sock|http://whodis-app/

    # Logging
    ErrorLog ${APACHE_LOG_DIR}/whodis_error.log
    CustomLog ${APACHE_LOG_DIR}/whodis_access.log combined
</VirtualHost>
```

## Security Hardening

### Application Security

1. **Environment Variables**
   ```bash
   # Set restrictive permissions on .env
   chmod 600 /home/whodis/whodis/.env
   chown whodis:whodis /home/whodis/whodis/.env
   ```

2. **Salt File Security**
   ```bash
   # Secure the encryption salt file
   chmod 600 /home/whodis/whodis/.whodis_salt
   chown whodis:whodis /home/whodis/whodis/.whodis_salt

   # Backup salt file securely (CRITICAL!)
   sudo cp /home/whodis/whodis/.whodis_salt /secure/backup/location/.whodis_salt.backup
   ```

3. **Disable Debug Mode**
   ```python
   # Via config
   config_set("flask", "debug", "false")
   ```

### Network Security

1. **Firewall Configuration (ufw)**
   ```bash
   # Enable firewall
   sudo ufw enable

   # Allow SSH (secure it with key-based auth only!)
   sudo ufw allow 22/tcp

   # Allow HTTP/HTTPS
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp

   # Allow PostgreSQL (only from app server if separate)
   sudo ufw allow from <app-server-ip> to any port 5432

   # Deny all other incoming
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   ```

2. **Fail2Ban for Brute Force Protection**
   ```bash
   sudo apt install -y fail2ban

   # Create WhoDis filter
   sudo nano /etc/fail2ban/filter.d/whodis.conf
   ```

   ```ini
   [Definition]
   failregex = Access denied for user .* from <HOST>
   ignoreregex =
   ```

   ```bash
   # Configure jail
   sudo nano /etc/fail2ban/jail.local
   ```

   ```ini
   [whodis]
   enabled = true
   port = http,https
   filter = whodis
   logpath = /var/log/whodis/access.log
   maxretry = 5
   bantime = 3600
   findtime = 600
   ```

   ```bash
   sudo systemctl restart fail2ban
   ```

### Database Security

1. **PostgreSQL Hardening**
   ```bash
   # Disable remote connections if not needed
   # In postgresql.conf:
   listen_addresses = 'localhost'

   # Require SSL connections
   # In postgresql.conf:
   ssl = on
   ssl_cert_file = '/path/to/server.crt'
   ssl_key_file = '/path/to/server.key'

   # In pg_hba.conf:
   hostssl    whodis_db    whodis_user    0.0.0.0/0    md5
   ```

2. **Regular Security Updates**
   ```bash
   # Enable automatic security updates
   sudo apt install -y unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades
   ```

## Monitoring and Logging

### Application Logging

**Log Locations:**
- Application logs: `/var/log/whodis/access.log`, `/var/log/whodis/error.log`
- Nginx logs: `/var/log/nginx/whodis.access.log`, `/var/log/nginx/whodis.error.log`
- PostgreSQL logs: `/var/log/postgresql/postgresql-*.log`

**Log Rotation:**
```bash
sudo nano /etc/logrotate.d/whodis
```

```
/var/log/whodis/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 whodis whodis
    sharedscripts
    postrotate
        systemctl reload supervisor > /dev/null 2>&1 || true
    endscript
}
```

### Database Audit Logging

WhoDis stores comprehensive audit logs in PostgreSQL:

**Query Audit Logs:**
```sql
-- Recent searches
SELECT * FROM audit_log
WHERE event_type = 'search'
ORDER BY timestamp DESC
LIMIT 100;

-- Failed access attempts
SELECT * FROM access_attempts
WHERE success = false
ORDER BY timestamp DESC;

-- Configuration changes
SELECT * FROM audit_log
WHERE event_type = 'config'
ORDER BY timestamp DESC;

-- Errors
SELECT * FROM error_log
ORDER BY timestamp DESC
LIMIT 50;
```

**Automated Reports:**
```bash
# Daily security report
cat > /home/whodis/scripts/daily_security_report.sh << 'EOF'
#!/bin/bash
psql -U whodis_user -d whodis_db -c "
SELECT
    event_type,
    COUNT(*) as count,
    DATE(timestamp) as date
FROM audit_log
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY event_type, DATE(timestamp)
ORDER BY date DESC, count DESC;
" | mail -s "WhoDis Daily Security Report" admin@example.com
EOF

chmod +x /home/whodis/scripts/daily_security_report.sh

# Add to crontab
crontab -e
# 0 6 * * * /home/whodis/scripts/daily_security_report.sh
```

### Health Monitoring

**Application Health Check:**
```bash
# Create health check endpoint monitor
cat > /home/whodis/scripts/health_check.sh << 'EOF'
#!/bin/bash
response=$(curl -s -o /dev/null -w "%{http_code}" https://whodis.example.com/)
if [ $response -ne 200 ]; then
    echo "WhoDis health check failed: HTTP $response" | mail -s "WhoDis Alert" admin@example.com
fi
EOF

chmod +x /home/whodis/scripts/health_check.sh

# Add to crontab (every 5 minutes)
# */5 * * * * /home/whodis/scripts/health_check.sh
```

**Database Connection Monitoring:**
```bash
# Monitor active connections
watch -n 60 'psql -U whodis_user -d whodis_db -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '\''whodis_db'\'';"'
```

## Backup and Disaster Recovery

### Database Backups

**Automated PostgreSQL Backups:**
```bash
# Create backup script
sudo mkdir -p /backup/whodis/database
sudo chown whodis:whodis /backup/whodis/database

cat > /home/whodis/scripts/backup_database.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backup/whodis/database"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/whodis_backup_$DATE.sql.gz"

# Backup database
pg_dump -U whodis_user -h localhost whodis_db | gzip > $BACKUP_FILE

# Keep only last 30 days of backups
find $BACKUP_DIR -name "whodis_backup_*.sql.gz" -mtime +30 -delete

# Verify backup was created
if [ -f "$BACKUP_FILE" ]; then
    echo "Backup successful: $BACKUP_FILE"
else
    echo "Backup failed!" | mail -s "WhoDis Backup Failed" admin@example.com
fi
EOF

chmod +x /home/whodis/scripts/backup_database.sh

# Schedule daily backups at 2 AM
crontab -e
# 0 2 * * * /home/whodis/scripts/backup_database.sh
```

**Encryption Key Backup:**
```bash
# CRITICAL: Backup encryption key and salt securely
# Store in multiple secure locations (encrypted USB drive, password manager, etc.)

# Export configuration (includes encrypted values)
python scripts/export_config.py > /secure/backup/whodis_config_$(date +%Y%m%d).json

# Backup .env file (contains WHODIS_ENCRYPTION_KEY)
sudo cp /home/whodis/whodis/.env /secure/backup/.env.backup_$(date +%Y%m%d)

# Backup salt file
sudo cp /home/whodis/whodis/.whodis_salt /secure/backup/.whodis_salt.backup_$(date +%Y%m%d)
```

### Disaster Recovery Procedures

**Database Restore:**
```bash
# Restore from backup
gunzip -c /backup/whodis/database/whodis_backup_20250101_020000.sql.gz | \
psql -U whodis_user -h localhost whodis_db
```

**Full System Recovery:**
1. Provision new server
2. Install PostgreSQL, Python, dependencies
3. Restore encryption key and salt files
4. Restore database from backup
5. Restore .env file with database credentials
6. Deploy application code
7. Verify configuration
8. Start services

**Recovery Time Objective (RTO):** 4 hours
**Recovery Point Objective (RPO):** 24 hours (daily backups)

## Post-Deployment Verification

### Smoke Tests

1. **Application Accessibility**
   ```bash
   curl -I https://whodis.example.com/
   # Should return HTTP 200
   ```

2. **Database Connectivity**
   ```bash
   python scripts/check_config_status.py
   # Should show "Configuration loaded successfully"
   ```

3. **Azure AD Authentication**
   - Navigate to https://whodis.example.com/
   - Verify Azure AD login prompt
   - Log in with test user
   - Check `/admin/users` for user provisioning

4. **API Integrations**
   ```bash
   # Check Genesys cache
   python scripts/check_genesys_cache.py

   # Test LDAP connection
   python scripts/diagnose_config.py
   ```

5. **Search Functionality**
   - Perform test search for known user
   - Verify results from LDAP, Genesys, Graph
   - Check phone number formatting
   - Verify photos load

6. **Admin Functions**
   - Access `/admin/configuration`
   - View audit logs at `/admin/audit-logs`
   - Test cache refresh buttons
   - Verify user management works

### Performance Baseline

**Establish Performance Metrics:**
```bash
# Time search response
time curl -s https://whodis.example.com/search?q=test.user > /dev/null

# Monitor database query performance
psql -U whodis_user -d whodis_db -c "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Check application response times
tail -f /var/log/nginx/whodis.access.log | awk '{print $NF}'
```

**Expected Performance:**
- Search response: < 2 seconds
- Page load: < 1 second
- Database queries: < 100ms average
- API token refresh: < 5 seconds

## Troubleshooting

### Common Issues

#### Application Won't Start

**Symptoms:** Supervisor shows `FATAL` state

**Check:**
```bash
sudo supervisorctl status whodis
sudo tail -50 /var/log/whodis/error.log
```

**Common Causes:**
- Missing `.env` file or incorrect permissions
- Database connection failure
- Python dependencies missing
- Port already in use

**Solution:**
```bash
# Verify .env exists and is readable
ls -la /home/whodis/whodis/.env

# Test database connection
psql -U whodis_user -d whodis_db -h localhost -c "SELECT 1;"

# Reinstall dependencies
cd /home/whodis/whodis
source venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo supervisorctl restart whodis
```

#### Database Connection Errors

**Symptoms:** "connection refused" or "authentication failed"

**Check:**
```bash
# PostgreSQL is running
sudo systemctl status postgresql

# Database exists
psql -U postgres -lqt | cut -d \| -f 1 | grep -qw whodis_db && echo "DB exists" || echo "DB missing"

# User can connect
psql -U whodis_user -d whodis_db -h localhost -c "SELECT version();"
```

**Solution:**
```bash
# Verify pg_hba.conf allows connection
sudo nano /etc/postgresql/12/main/pg_hba.conf
# Add: host    whodis_db    whodis_user    127.0.0.1/32    md5

# Reload PostgreSQL
sudo systemctl reload postgresql

# Check .env credentials match database user
cat /home/whodis/whodis/.env | grep POSTGRES
```

#### SSL/TLS Certificate Errors

**Symptoms:** Browser shows certificate warnings

**Check:**
```bash
# Certificate expiration
openssl x509 -in /etc/ssl/certs/whodis.example.com.crt -noout -dates

# Certificate matches domain
openssl x509 -in /etc/ssl/certs/whodis.example.com.crt -noout -subject
```

**Solution:**
```bash
# Renew Let's Encrypt certificate
sudo certbot renew

# Reload nginx
sudo systemctl reload nginx
```

#### Slow Search Performance

**Symptoms:** Searches take > 5 seconds

**Diagnose:**
```bash
# Check database query performance
psql -U whodis_user -d whodis_db -c "
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;"

# Check API token status
curl -s https://whodis.example.com/admin/cache | grep token

# Monitor concurrent search timeouts
tail -f /var/log/whodis/access.log | grep "search"
```

**Solutions:**
- Run `VACUUM ANALYZE` on database
- Refresh API tokens: `/admin/cache` → Refresh buttons
- Check network latency to LDAP/Genesys/Graph
- Increase timeout values in configuration
- Check for expired cache entries

### Getting Support

**Before Contacting Support:**
1. Check [docs/database.md](database.md#troubleshooting)
2. Review application logs
3. Check audit logs for errors
4. Verify configuration

**Collect Diagnostic Information:**
```bash
# System information
uname -a
python --version
psql --version

# Application status
sudo supervisorctl status whodis
sudo systemctl status nginx
sudo systemctl status postgresql

# Recent errors
sudo tail -100 /var/log/whodis/error.log
sudo tail -100 /var/log/nginx/whodis.error.log
```

**Contact:**
- GitHub Issues: https://github.com/jslitzkerttcu/Who-Dis/issues
- Security Issues: See [SECURITY.md](../SECURITY.md)

---

## Additional Resources

- **Architecture**: [docs/architecture.md](architecture.md)
- **Database**: [docs/database.md](database.md)
- **Security**: [SECURITY.md](../SECURITY.md)
- **Contributing**: [CONTRIBUTING.md](../CONTRIBUTING.md)
- **Changelog**: [CHANGELOG.md](../CHANGELOG.md)

---

*Last Updated: December 29, 2025*
