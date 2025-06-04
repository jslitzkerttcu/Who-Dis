# WhoDis - Identity Lookup Service

A Flask-based web application for identity lookup with role-based access control (RBAC) and Azure AD integration.

## Overview

WhoDis is a secure identity lookup service that allows authorized users to search for people by various criteria including full name, email address, phone number, and username. The application features a robust authentication system with three role levels and comprehensive access logging.

## Features

- **Role-Based Access Control (RBAC)** with three tiers:
  - **Viewers**: Basic search access
  - **Editors**: Enhanced permissions (to be implemented)
  - **Admins**: Full system access including admin panel
- **Azure AD Integration** for enterprise authentication
- **Fallback HTTP Basic Authentication**
- **Access Denial Logging** with humorous messages
- **Responsive Bootstrap UI**
- **Modular Blueprint Architecture**

## Tech Stack

- **Backend**: Flask 3.0.0 (Python)
- **Frontend**: Bootstrap 5.3.0, Bootstrap Icons
- **Authentication**: Azure AD / Basic Auth
- **Template Engine**: Jinja2
- **Environment Management**: python-dotenv

## Installation

1. Clone the repository:
```bash
git clone https://github.com/jslitzkerttcu/Who-Dis.git
cd Who-Dis
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
   - Copy `.env.example` to `.env` (if available) or create `.env` with:
```env
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here
VIEWERS=user1@example.com,user2@example.com
EDITORS=editor1@example.com,editor2@example.com
ADMINS=admin@example.com
```

## Usage

Run the application:
```bash
python run.py
```

The application will be available at `http://localhost:5000`

## Project Structure

```
WhoDis/
├── app/                    # Main application package
│   ├── blueprints/         # Flask blueprints
│   │   ├── admin/         # Admin panel (requires admin role)
│   │   ├── home/          # Landing page
│   │   └── search/        # Search interface (requires viewer role)
│   ├── middleware/        # Authentication middleware
│   │   └── auth.py        # RBAC implementation
│   ├── static/            # CSS and JavaScript
│   └── templates/         # Jinja2 templates
├── logs/                  # Application logs
│   └── access_denied.log  # Unauthorized access attempts
├── run.py                 # Application entry point
└── requirements.txt       # Python dependencies
```

## Authentication

The application supports two authentication methods:

1. **Azure AD** (Primary): Automatically detects user via `X-MS-CLIENT-PRINCIPAL-NAME` header
2. **Basic Auth** (Fallback): Username/password authentication

Users must be whitelisted in the `.env` file under the appropriate role category.

## Security

- Change the `SECRET_KEY` in production
- All access denials are logged with timestamp, user email, IP address, and requested path
- User access is managed via environment variable whitelists
- Sensitive files (.env, logs) are excluded from version control

## Development Status

- ✅ Authentication and authorization system
- ✅ Role-based access control
- ✅ Basic UI framework
- ✅ Logging system
- ⏳ Search functionality (placeholder - to be implemented)
- ⏳ Editor role features (to be defined)
- ⏳ Database integration

## Contributing

This project is in active development. Key areas for contribution:
- Implementing the search functionality
- Defining and implementing editor role capabilities
- Adding database integration for identity storage
- Implementing comprehensive test coverage

## License

[License information to be added]

## Authors

- TTCU Development Team