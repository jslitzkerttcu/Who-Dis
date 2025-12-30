# Security Policy

## Supported Versions

We actively maintain and provide security updates for the following versions of WhoDis:

| Version | Supported          |
| ------- | ------------------ |
| 2.1.x   | :white_check_mark: |
| 2.0.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

We take the security of WhoDis seriously. If you discover a security vulnerability, please follow these steps:

### 1. **Do Not** Open a Public Issue

Please do not report security vulnerabilities through public GitHub issues. This helps protect users who haven't yet updated.

### 2. Report Privately

**Preferred Method:** Use GitHub's private vulnerability reporting feature:
1. Go to the [Security tab](https://github.com/jslitzkerttcu/Who-Dis/security)
2. Click "Report a vulnerability"
3. Fill out the vulnerability details

**Alternative Method:** Email us directly at **jslitzker@gmail.com** with:
- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact
- Any suggested fixes (if available)

### 3. What to Expect

- **Acknowledgment:** We'll acknowledge receipt within 48 hours
- **Assessment:** We'll assess the vulnerability and determine severity within 5 business days
- **Updates:** We'll keep you informed of our progress
- **Resolution:** We'll work on a fix and coordinate disclosure timing with you
- **Credit:** We'll credit you in the security advisory (unless you prefer to remain anonymous)

## Security Best Practices

### For Deployment

When deploying WhoDis in production, ensure you follow these security practices:

#### 1. **Environment Variables**
- Never commit `.env` files to version control
- Use strong, unique values for `WHODIS_ENCRYPTION_KEY`
- Rotate encryption keys periodically (with proper migration)
- Store `.whodis_salt` file securely and back it up

#### 2. **Database Security**
- Use strong PostgreSQL passwords (20+ characters, mixed case, numbers, symbols)
- Enable SSL/TLS for database connections in production
- Restrict database access to application servers only
- Regularly backup encrypted configuration data

#### 3. **Authentication**
- Use Azure AD SSO exclusively (basic auth is disabled)
- Implement proper role-based access control (Admin, Editor, Viewer)
- Monitor failed authentication attempts in audit logs
- Configure session timeouts appropriately (default: 15 minutes)

#### 4. **Network Security**
- Run behind HTTPS reverse proxy (nginx, Apache, Azure App Proxy)
- Implement rate limiting to prevent brute force attacks
- Use firewall rules to restrict access to trusted networks
- Enable security headers (CSP, X-Frame-Options, etc.) - already configured

#### 5. **API Credentials**
- Store all API credentials encrypted in database (never in code)
- Use service accounts with minimal required permissions
- Rotate API credentials regularly
- Monitor API usage and quotas

#### 6. **Audit Logging**
- Regularly review audit logs for suspicious activity
- Set up alerts for critical events (failed auth, config changes)
- Retain audit logs for compliance requirements (default: 90 days)
- Export and archive logs for long-term storage

### For Development

#### 1. **Code Security**
- Never hardcode credentials or secrets
- Use parameterized queries (SQLAlchemy ORM handles this)
- Validate and sanitize all user input
- Use `escapeHtml()` function in templates to prevent XSS
- Follow OWASP Top 10 security practices

#### 2. **Dependency Management**
- Keep dependencies up to date (check monthly)
- Run `pip-audit` regularly to check for vulnerabilities
- Review Dependabot alerts and apply fixes promptly
- Pin dependency versions in `requirements.txt`

#### 3. **Code Review**
- All code changes should be reviewed before merging
- Pay special attention to authentication/authorization changes
- Review SQL queries for potential injection vulnerabilities
- Check for information disclosure in error messages

## Security Features

WhoDis includes several built-in security features:

### Data Protection
- **Encryption at Rest:** All sensitive configuration encrypted with Fernet
- **Unique Salts:** Each installation uses a unique encryption salt
- **Secure Sessions:** Flask sessions with CSRF protection
- **Password Security:** LDAP password data prioritized over Graph API

### Access Control
- **Role-Based Access (RBAC):** Admin, Editor, Viewer hierarchy
- **Azure AD Integration:** Single sign-on with enterprise directory
- **Session Timeouts:** Configurable inactivity timeouts with warnings
- **Access Logging:** All authentication attempts logged with full context

### Security Headers
- **Content Security Policy (CSP):** Prevents XSS attacks
- **X-Frame-Options:** Prevents clickjacking
- **X-Content-Type-Options:** Prevents MIME sniffing
- **Referrer-Policy:** Controls referrer information
- **Permissions Policy:** Disables unnecessary browser features

### Audit Trail
- **Comprehensive Logging:** All searches, access attempts, and config changes logged
- **Immutable Logs:** Audit logs stored in PostgreSQL with timestamps
- **User Attribution:** All actions tracked with user email, IP, user agent
- **Query Capability:** Indexed audit logs for fast security investigations

## Known Security Considerations

### 1. **Encryption Key Management**
- Changing `WHODIS_ENCRYPTION_KEY` makes all encrypted data unreadable
- Always export configuration before key rotation
- Store encryption key in secure secret management system
- Document key rotation procedures in operational runbooks

### 2. **Database Bootstrap**
- PostgreSQL credentials must remain in `.env` (bootstrap requirement)
- Secure `.env` file with appropriate file permissions (600)
- Never commit `.env` to version control (GitHub push protection enabled)

### 3. **Token Storage**
- API tokens stored encrypted in `api_tokens` table
- Tokens automatically refreshed by background service
- Expired tokens cleaned up automatically
- Monitor token refresh failures in error logs

### 4. **Search Result Caching**
- Search results cached for 30 minutes in database
- Cache includes user data from multiple systems
- Old cache entries automatically cleaned up
- Consider cache implications for sensitive data

## Security Update Process

When we release security updates:

1. **Severity Assessment:** We classify vulnerabilities as Critical, High, Medium, or Low
2. **Patch Development:** We develop and test fixes in a private branch
3. **Security Advisory:** We publish a GitHub Security Advisory
4. **Release:** We release a new version with the fix
5. **Notification:** We notify users through release notes and CHANGELOG.md
6. **Disclosure:** We publicly disclose details after users have had time to update

## Vulnerability Disclosure Timeline

- **Day 0:** Vulnerability reported
- **Day 2:** Acknowledgment sent to reporter
- **Day 7:** Severity assessment completed
- **Day 30:** Fix developed and tested (may vary based on complexity)
- **Day 35:** Security advisory published and patch released
- **Day 90:** Full public disclosure (earlier if patch is widely deployed)

## Security Resources

- **OWASP Top 10:** https://owasp.org/www-project-top-ten/
- **Flask Security:** https://flask.palletsprojects.com/en/latest/security/
- **SQLAlchemy Security:** https://docs.sqlalchemy.org/en/latest/core/security.html
- **Python Security:** https://python.readthedocs.io/en/latest/library/security_warnings.html

## Contact

For security issues: **jslitzker@gmail.com**

For general issues: [GitHub Issues](https://github.com/jslitzkerttcu/Who-Dis/issues)

---

*Last Updated: December 29, 2025*
