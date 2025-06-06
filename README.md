# 🕵️‍♂️ WhoDis - Enterprise Identity Search Platform

A comprehensive Flask-based identity lookup service that searches across Active Directory, Microsoft Graph, and Genesys Cloud. Features concurrent searches, smart matching, and a modern UI with role-based access control.

---

## 🚀 What's New

**WhoDis** has evolved from a simple LDAP lookup tool to a full-featured identity search platform that integrates with multiple enterprise systems:

- **🔍 Multi-Source Search**: Simultaneously searches LDAP, Microsoft Graph (Azure AD), and Genesys Cloud
- **🧠 Smart Matching**: Automatically matches users across systems by email when dealing with multiple results
- **📸 Profile Photos**: Fetches user photos from Microsoft Graph API
- **🔐 Password Insights**: Shows password expiration and last changed dates from Active Directory
- **📱 Modern UI**: Clean two-column layout with rounded search bar and custom branding
- **⚡ Lightning Fast**: Concurrent API calls with configurable timeouts prevent hanging searches

---

## 🎯 Key Features

### Search Capabilities
* **Fuzzy Search**: LDAP supports wildcard searches for partial name/email matches
* **Concurrent Processing**: All three services searched simultaneously with timeout protection
* **Smart Result Matching**: When one service returns a single result and another returns multiple, automatically matches by email
* **Multiple Result Handling**: Clean selection interface when multiple matches are found

### Data Integration
* **Azure AD Card**: Combines LDAP and Microsoft Graph data with Graph taking priority
* **Enhanced Fields**: Hire dates, birth dates, password policies, token refresh times
* **Phone Number Tags**: Visual indicators showing source (Genesys/Teams)
* **Date Formatting**: Smart relative dates (e.g., "6Yr 8Mo ago") with military time

### UI/UX Features
* **Status Badges**: Visual indicators for Enabled/Disabled and Locked/Not Locked accounts
* **Collapsible Groups**: AD and Genesys groups in expandable sections to reduce clutter
* **Profile Photos**: Centered display with status badges positioned absolutely
* **Custom Branding**: TTCU green (#007c59) for Azure AD, Genesys orange (#FF4F1F), and golden buttons (#f2c655)
* **Modern Search Bar**: Pill-shaped design with subtle shadow effects

---

## 🛠 Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | Flask 3.0.0 | Web framework |
| Authentication | Azure AD / Basic Auth | User authentication |
| LDAP | ldap3 | Active Directory integration |
| Graph API | MSAL + requests | Microsoft Graph integration |
| Genesys | OAuth2 + requests | Contact center data |
| Frontend | Bootstrap 5.3.0 | UI components |
| Templating | Jinja2 | Dynamic HTML generation |
| Environment | python-dotenv | Configuration management |

---

## 🚀 Quick Start

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

4. **Configure environment** (see detailed .env example below):
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the application**:
   ```bash
   python run.py
   ```

   Access at [http://localhost:5000](http://localhost:5000)

---

## 📋 Environment Configuration

Create a `.env` file with the following configuration:

```env
# Flask Configuration
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=True
SECRET_KEY=your-very-secret-key-change-this

# User Access Control (comma-separated emails)
VIEWERS=viewer1@example.com,viewer2@example.com
EDITORS=editor@example.com
ADMINS=admin@example.com

# LDAP Configuration
LDAP_HOST=ldap://your-dc.example.com
LDAP_PORT=389
LDAP_USE_SSL=False
LDAP_BIND_DN=CN=service_account,OU=Service Accounts,DC=example,DC=com
LDAP_BIND_PASSWORD=your-service-account-password
LDAP_BASE_DN=DC=example,DC=com
LDAP_USER_SEARCH_BASE=OU=Employees,DC=example,DC=com
LDAP_CONNECT_TIMEOUT=5
LDAP_OPERATION_TIMEOUT=10

# Genesys Cloud Configuration
GENESYS_CLIENT_ID=your-oauth-client-id
GENESYS_CLIENT_SECRET=your-oauth-client-secret
GENESYS_REGION=mypurecloud.com  # or mypurecloud.ie, etc.
GENESYS_API_TIMEOUT=15

# Microsoft Graph Configuration
GRAPH_CLIENT_ID=your-app-registration-client-id
GRAPH_CLIENT_SECRET="your-client-secret-with-special-chars"
GRAPH_TENANT_ID=your-tenant-id
GRAPH_API_TIMEOUT=15

# Search Configuration
SEARCH_OVERALL_TIMEOUT=20  # Maximum time for all searches combined
```

### Important Notes:
- **Graph Client Secret**: If your secret contains special characters (especially `=`), wrap it in quotes
- **LDAP Bind DN**: Use a service account with read permissions on user objects
- **Genesys Region**: Check your Genesys Cloud URL to determine the correct region
- **Timeouts**: Adjust based on your network latency and API response times

---

## 🗂 Project Structure

```
WhoDis/
├── app/                      # Application code
│   ├── __init__.py          # Flask app factory
│   ├── blueprints/          # Route handlers
│   │   ├── admin/           # Admin panel (user management)
│   │   ├── home/            # Landing page
│   │   └── search/          # Search interface and logic
│   ├── middleware/          # Authentication and authorization
│   │   └── auth.py          # RBAC implementation
│   ├── services/            # External service integrations
│   │   ├── ldap_service.py  # Active Directory queries
│   │   ├── genesys_service.py    # Genesys Cloud API
│   │   ├── genesys_cache.py      # OAuth token caching
│   │   └── graph_service.py      # Microsoft Graph API
│   ├── static/              # CSS, JS, images
│   │   ├── css/             # Custom styles
│   │   ├── js/              # Client-side logic
│   │   └── img/             # Logos and icons
│   └── templates/           # Jinja2 HTML templates
├── logs/                    # Application logs
│   └── access_denied.log    # Failed auth attempts
├── requirements.txt         # Python dependencies
├── run.py                  # Application entry point
├── .env                    # Environment configuration
└── CLAUDE.md               # AI assistant guidelines
```

---

## 🔐 Authentication & Authorization

### Authentication Methods
1. **Azure AD (Primary)**: Checks `X-MS-CLIENT-PRINCIPAL-NAME` header from Azure App Service
2. **Basic Auth (Fallback)**: Username/password for development or non-Azure environments

### Role Hierarchy
- **👀 Viewers**: Can search and view user information
- **🛠 Editors**: Can search, view, and modify user data (future feature)
- **👑 Admins**: Full access including user management panel

### Access Control
- Users must be whitelisted in the `.env` file
- Failed access attempts are logged with humorous messages
- Unauthorized users see a full-screen "NOPE" page

---

## 🔍 Search Features Explained

### Concurrent Search
All three services (LDAP, Genesys, Graph) are queried simultaneously using Python's ThreadPoolExecutor. If any service times out, others continue returning results.

### Smart Matching
When searching returns:
- **Single LDAP + Multiple Genesys**: Automatically matches by email
- **Multiple LDAP + Single Graph**: Finds the matching LDAP entry
- **Manual Selection**: Clean UI for choosing from multiple matches

### Data Merging
Azure AD card intelligently combines:
- **LDAP**: Base user data, password expiration, group membership
- **Graph**: Enhanced fields, profile photo, hire dates
- **Priority**: Graph data overwrites LDAP when both exist

---

## 🎨 UI Customization

### Brand Colors
- **Azure AD Header**: TTCU Green (#007c59)
- **Genesys Header**: Genesys Orange (#FF4F1F)  
- **Buttons**: Golden Yellow (#f2c655)
- **Phone Tags**: Service-specific colors

### Modern Design Elements
- Rounded search bar with shadow
- Status badges positioned as presence indicators
- Responsive two-column layout
- Collapsible sections for long lists
- Smart date formatting (6Yr 8Mo ago vs 2430 days)

---

## 📊 API Integrations

### LDAP/Active Directory
- Searches by username, email, display name
- Retrieves password expiration from computed attributes
- Supports fuzzy matching with wildcards
- Handles large result sets with pagination

### Microsoft Graph (Beta API)
- Enhanced user profiles with hire dates
- Binary photo retrieval and base64 encoding
- Manager relationships with expansion
- Token refresh and session validity times

### Genesys Cloud
- OAuth2 client credentials flow
- User skills, queues, and locations
- Multiple phone number types
- Automatic token refresh with caching

---

## 🚨 Security Considerations

1. **Change the SECRET_KEY** in production
2. **Use HTTPS** for all deployments
3. **Rotate API credentials** regularly
4. **Monitor access logs** for suspicious activity
5. **Validate Graph secrets** - wrap in quotes if they contain special characters
6. **Use service accounts** with minimal required permissions

---

## 🐛 Troubleshooting

### Common Issues

**"No results found"**
- Check LDAP bind credentials
- Verify user exists in search base OU
- Try searching with full email address

**"Search timed out"**
- Increase timeout values in .env
- Check network connectivity to services
- Use more specific search terms

**Missing Graph data/photos**
- Verify Graph API permissions (User.Read.All)
- Check if beta API endpoints are needed
- Ensure app registration has proper consent

**Genesys authentication failures**
- Verify OAuth client credentials
- Check Genesys region setting
- Ensure IP is whitelisted in Genesys

---

## 📈 Performance Tips

1. **Adjust Timeouts**: Balance between responsiveness and completeness
2. **Cache Strategy**: Genesys tokens are cached; consider caching Graph tokens
3. **Limit Results**: Configure maximum results per service
4. **Index Optimization**: Ensure LDAP has proper indexes on search fields

---

## 🧑‍💻 Contributing

We welcome contributions! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request with clear description

---

## 📝 Future Enhancements

- [ ] Redis caching for improved performance
- [ ] Bulk user operations
- [ ] Export search results to CSV/Excel
- [ ] Advanced search filters
- [ ] Real-time presence indicators
- [ ] Mobile-responsive design improvements
- [ ] GraphQL API endpoint
- [ ] Audit trail for all searches

---

## ⚖️ License

[Insert your license here]

---

## 🙏 Acknowledgments

Built with ❤️ by the TTCU Development Team

Special thanks to all contributors who helped evolve WhoDis from a simple LDAP tool to a comprehensive identity platform.

---

*For detailed technical documentation and AI assistant guidelines, see [CLAUDE.md](CLAUDE.md)*