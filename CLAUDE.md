# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
# Set up virtual environment (if not already created)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

The application runs on http://localhost:5000 with debug mode enabled.

### Testing
No test framework is currently configured. When implementing tests, consider adding pytest to requirements.txt.

### Linting
No linter is currently configured. Consider adding flake8 or pylint to the project.

## Architecture

### Application Structure
WhoDis is a Flask-based identity lookup service with role-based access control. The application uses a blueprint architecture for modularity:

- **`app/__init__.py`**: Application factory that initializes Flask, loads environment config, and registers blueprints
- **`app/blueprints/`**: Contains three main blueprints:
  - `home`: Landing page (requires authentication)
  - `search`: Identity search interface (requires 'viewer' role minimum)
  - `admin`: Admin panel (requires 'admin' role)
- **`app/middleware/auth.py`**: Implements role-based authentication with Azure AD integration and fallback to basic auth

### Authentication Flow
1. Primary authentication via Azure AD (`X-MS-CLIENT-PRINCIPAL-NAME` header)
2. Fallback to HTTP basic authentication
3. Users are whitelisted in `.env` file under VIEWERS, EDITORS, and ADMINS
4. Role hierarchy: Admin > Editor > Viewer
5. Access denials are logged to `logs/access_denied.log` with humorous messages

### Key Implementation Notes
- Search functionality is currently a placeholder - the actual search logic needs to be implemented
- User roles are managed via environment variables in `.env`
- The application uses Flask's `g` object for request-scoped user data
- All templates extend from `base.html` using Jinja2 inheritance
- Bootstrap 5.3.0 is used for styling

### Security Considerations
- Change `SECRET_KEY` in `.env` before production deployment
- Current authentication relies on email whitelisting
- All unauthorized access attempts are logged with timestamp, user, IP, and requested path