# WhoDis Project Planning

## Overview
A comprehensive Flask-based identity lookup service that provides IT support staff with a unified interface for user identity management across Active Directory, Microsoft Graph, Genesys Cloud, and consolidated employee data systems. Features modern hybrid server-side rendering with HTMX for dynamic interactions.

## Problem & Goal
**Problem**: IT staff need to access multiple disparate systems to view and manage user account information, leading to inefficiency and potential errors.

**Target Users**: Internal IT service desk team (4-5 technical users) with role-based access (Admin/Editor/Viewer)

**Primary Goal**: Unified interface for viewing backend system data points on user accounts with role-based write capabilities and comprehensive reporting.

## Current Architecture (As Implemented)

### Core Components
- **Flask Application**: Hybrid server-side rendering with HTMX for dynamic updates
- **Auth Service**: Azure AD SSO with header passthrough and database-backed user management
- **Service Layer**: Integrated modules for LDAP, Graph, Genesys with unified base classes
- **Database Layer**: PostgreSQL with encrypted configuration and comprehensive audit logging
- **Cache System**: Database-backed caching with automatic expiration and background refresh
- **Session Management**: Timeout tracking with warning modals and activity monitoring

### Technology Stack (Current Implementation)

#### Backend
- **Framework**: Flask 3.0.0 with blueprint architecture
- **Database**: PostgreSQL with SQLAlchemy ORM and encrypted configuration storage
- **Authentication**: Azure AD SSO with role-based access control
- **API Integrations**: LDAP (python-ldap), Graph API (MSAL), Genesys Cloud (OAuth2)
- **Background Services**: Token refresh and cache management

#### Frontend (Hybrid Architecture)
- **Server-Side**: Jinja2 templates with Tailwind CSS
- **Dynamic Updates**: HTMX for seamless interactions without page refreshes
- **Progressive Enhancement**: Works without JavaScript, enhanced with HTMX
- **Mobile-First**: Responsive design with touch-friendly interfaces
- **Icons**: FontAwesome for visual hierarchy

#### External Integrations
- **Active Directory**: LDAP with fuzzy search and timeout handling
- **Microsoft Graph**: Beta APIs with photo retrieval and enhanced profile data
- **Genesys Cloud**: Contact center data with cached groups, skills, and locations
- **Employee Profiles**: Consolidated data architecture replacing legacy systems

### Communication Flow
```
[Browser] → [Azure App Proxy (X-Headers)] → [Flask App]
                                                ↓
                                        [Auth Middleware]
                                                ↓
                                        [Blueprint Router]
                                        ↙    ↓    ↓    ↘
                                [Home] [Search] [Admin] [Session]
                                                ↓
                                        [Service Layer]
                                        ↙    ↓    ↓    ↘
                                [LDAP] [Graph] [Genesys] [Employee Profiles]
                                                ↓
                                        [PostgreSQL Cache]
                                                ↓
                                        [Comprehensive Audit Log]
```

### Data Flow
1. HTMX sends requests for HTML fragments
2. Flask validates Azure AD headers and database user roles
3. Services check PostgreSQL cache first (with configurable TTL)
4. On cache miss, query external systems with timeout handling
5. Update cache and return server-rendered HTML fragments
6. Log all operations to audit table with full context
7. Background services refresh tokens and cache automatically

## Design Principles (Implemented)

### Performance
- **Sub-2 Second Response**: Multi-system lookups optimized with concurrent requests
- **Smart Caching**: PostgreSQL-backed with automatic expiration and background refresh
- **Progressive Loading**: HTMX enables partial page updates without full refreshes
- **Background Services**: Automatic token refresh and cache management

### Security & Compliance
- **Comprehensive Audit**: All actions logged (searches, access, config changes, errors)
- **Encrypted Storage**: Fernet encryption for all sensitive configuration data
- **Role-Based Access**: Admin/Editor/Viewer hierarchy with granular permissions
- **Session Security**: Timeout tracking with extension capability and SSO integration
- **XSS Protection**: Comprehensive input escaping and security headers

### User Experience
- **Modern Interface**: Card-based layouts with hover tooltips and status indicators
- **Mobile-First**: Responsive design that works on all devices
- **Real-Time Updates**: HTMX provides SPA-like experience with server-side benefits
- **Session Management**: Warning modals with countdown timers for timeout prevention

## Current Status (Delivered Features)

### ✅ Foundation (Complete)
- Flask application with blueprint architecture
- Encrypted configuration management with database storage
- PostgreSQL schema with comprehensive audit tables
- Azure AD SSO authentication with role-based access
- Unified employee profile cards (minimal data fields currently utilized)
- Multi-system integration (Active Directory, Microsoft Graph, Genesys Cloud)
- Hybrid Jinja2/HTMX frontend with responsive mobile-first design
- Audit logging and session management

### ⚠️ Known Gaps
- Unified profile cards need expansion: currently minimal data fields from Genesys, Azure, and AD are shown, despite broader data availability
- Reporting is basic and does not leverage full scope of Graph APIs or Genesys data
- No advanced analytics or cross-system correlation yet implemented

---
- Session management with timeout and activity tracking

### ✅ Multi-System Integration (Complete)
- LDAP integration with fuzzy search and account status
- Microsoft Graph integration with enhanced profile data and photos
- Genesys Cloud integration with skills, groups, and contact center data
- Consolidated employee profiles architecture
- Concurrent search across all systems with smart result matching

### ✅ Modern UI & Admin (Complete)
- Hybrid server-side + HTMX architecture for optimal performance
- Responsive search interface with real-time results
- Modern admin interface with cache management and user controls
- Comprehensive audit log viewer with filtering and search
- Session timeout warnings with extension capability

### ✅ Write Operations (Partial)
- Genesys blocked number management (CRUD operations)
- Configuration management through admin interface
- User management with role assignment
- Cache control and refresh capabilities

## Roadmap & Future Milestones

### Phase 1: Enhanced Data Integration (High Priority)
**Goal:** Make unified profile cards robust by leveraging all available data fields from Genesys, Azure AD, and Graph APIs.

- Expand Azure AD/Graph profile fields: department, cost center, employee ID, hire date, manager chain, sign-in activity, licenses, group memberships, device registrations, authentication methods, MFA status
- Genesys: add historical metrics, schedule adherence, skill proficiency, call logs, queue stats
- Cross-system correlation: match users across AD, Graph, Genesys; resolve duplicates
- Data quality scoring and field-level validation
- UI: show more fields, allow filtering, and export (CSV/Excel)

### Phase 2: Comprehensive Reporting Suite (High Priority)
**Goal:** Leverage Graph/Genesys APIs for rich reporting and dashboards.

- Azure AD: license utilization/expiry, unused licenses, group analytics, login and device activity, MFA adoption, risky sign-ins, privileged accounts
- Security: Advanced Threat Protection, guest user access, secure score, access reviews
- Email/Exchange: mailbox analytics, mail flow, phishing/spam, out-of-office status
- Teams: usage, call logs, membership, inactive users, external sharing
- SharePoint/OneDrive: storage, activity, external sharing, site usage
- PowerBI: dashboard/report usage, dataset refresh, workspace metrics
- Admin: schedule reports, export, and alerting

### Phase 3: Advanced User Management & Automation (Medium Priority)
**Goal:** Expand write operations and automate workflows.

- AD: account lock/unlock, password reset, group management
- Graph: license assignment/removal, attribute sync
- Genesys: queue management, agent performance, contact center analytics
- Workflow automation: onboarding/offboarding, provisioning, scheduled reports, alerts, self-service portal

### Phase 4: Job Role Compliance Matrix (High Priority for Compliance)
**Goal:** Ensure audit and compliance through mapping job codes/titles to expected system roles and automated privilege checking.

#### Core Functionality
- Map job codes/titles to expected system roles
- Bulk compliance checking across all systems
- Automated detection of missing or extra privileges

#### Smart Features
- Historical tracking with full audit trail
- Caching for performance

#### Admin Experience
- Visual matrix editor with drag-and-drop interface
- CSV import/export for bulk updates
- Compliance dashboard with actionable insights
- Version control for mapping changes

#### Integration Points
- Pull actual roles from Data Warehouse via SQL queries
- Sync all possible Job Codes and Roles from warehouse with a sync button
- Real-time comparison against expected roles

### Phase 5: Integration & Ecosystem (Medium Priority)
**Goal:** Integrate with ITSM, HR, and asset management systems.

- Ticketing: auto-case creation, status sync
- HR: lifecycle and org chart sync
- Asset/network: user-centric analytics
- RESTful API for third-party integrations

### Phase 5: Advanced Analytics & AI (Long-Term)
**Goal:** Predictive analytics, AI-powered features, and intelligent recommendations.

- Usage forecasting, risk assessment, anomaly detection
- Natural language search, chatbot interface, automated insights

---

## Suggestions for Continuous Improvement
- Prioritize expanding unified profile cards with all available data fields from each source
- Build modular reporting widgets/dashboards for each major data domain (AD, Graph, Genesys, Email, Teams, SharePoint, PowerBI)
- Add admin UI for configuring scheduled reports and alerts
- Plan for security/compliance reporting as a core feature, not an add-on
- Document all new API endpoints and data fields as they are added
- Regularly review and update the roadmap based on user feedback and new data availability

This roadmap represents a strategic evolution from the current identity lookup service to a comprehensive IT management platform, leveraging the robust foundation already built while expanding capabilities to meet growing organizational needs.