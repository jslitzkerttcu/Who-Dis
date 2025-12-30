# Contributing to WhoDis

Thank you for your interest in contributing to WhoDis! This document provides guidelines and instructions for contributing to the project.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Documentation](#documentation)
- [Questions and Support](#questions-and-support)

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Accept constructive criticism gracefully
- Focus on what's best for the project and community
- Show empathy towards other contributors
- Respect differing viewpoints and experiences

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Trolling or insulting/derogatory comments
- Public or private harassment
- Publishing others' private information without permission

## Getting Started

### Prerequisites

Before you begin, ensure you have:
- **Python 3.8+** installed
- **PostgreSQL 12+** installed and running
- **Git** for version control
- A **code editor** (VS Code, PyCharm, etc.)
- Basic knowledge of Flask, SQLAlchemy, and PostgreSQL

### Development Setup

1. **Fork and Clone the Repository**
   ```bash
   git fork https://github.com/jslitzkerttcu/Who-Dis.git
   cd Who-Dis
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Database**
   ```bash
   # Create PostgreSQL database and user
   psql -U postgres
   ```
   ```sql
   CREATE DATABASE whodis_db;
   CREATE USER whodis_user WITH PASSWORD 'your_dev_password';
   GRANT ALL PRIVILEGES ON DATABASE whodis_db TO whodis_user;
   \q
   ```
   ```bash
   # Create tables
   psql -U whodis_user -d whodis_db -h localhost -f database/create_tables.sql

   # Analyze tables for statistics
   psql -U postgres -d whodis_db -h localhost -f database/analyze_tables.sql
   ```

5. **Configure Environment Variables**

   Create a `.env` file in the project root:
   ```bash
   # PostgreSQL Configuration
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=whodis_db
   POSTGRES_USER=whodis_user
   POSTGRES_PASSWORD=your_dev_password

   # Encryption key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
   WHODIS_ENCRYPTION_KEY=your-generated-encryption-key
   ```

6. **Verify Installation**
   ```bash
   python scripts/check_config_status.py
   python scripts/verify_encrypted_config.py
   ```

7. **Run the Application**
   ```bash
   python run.py
   ```

   Application should be running at http://localhost:5000

### Understanding the Codebase

Before making changes, familiarize yourself with:
- **[CLAUDE.md](CLAUDE.md)** - Development patterns and quick reference
- **[docs/architecture.md](docs/architecture.md)** - System architecture and design patterns
- **[docs/database.md](docs/database.md)** - Database schema and management
- **[README.md](README.md)** - Project overview and features

## Development Workflow

### Branch Strategy

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-number-description
   ```

2. **Make Your Changes**
   - Write clean, well-documented code
   - Follow the code standards below
   - Test your changes thoroughly

3. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "type: brief description

   Detailed explanation of changes

   🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Your Name <your.email@example.com>"
   ```

4. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your fork and branch
   - Fill out the PR template with details

### Commit Message Convention

We follow a semantic commit message format:

```
type: brief description (max 50 chars)

Detailed explanation of what changed and why.
Can be multiple paragraphs.

- Bullet points for specific changes
- Reference issues with #issue-number

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Your Name <your.email@example.com>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic changes)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, build, etc.)
- `security`: Security fixes or improvements

**Examples:**
```
feat: add bulk user export functionality

Added CSV export capability for search results with configurable fields
and role-based access control.

- Created export service with field selection
- Added admin-only export route
- Implemented CSV streaming for large datasets
```

```
fix: resolve N+1 query in job codes table

Replaced individual relationship queries with single bulk query to
eliminate performance bottleneck on job codes management page.

Fixes #123
```

## Code Standards

### Python Code Style

We use **ruff** for linting and **mypy** for type checking.

**Before committing, run:**
```bash
# Linting
ruff check --fix

# Type checking
mypy app/ scripts/

# Format code (optional)
black .
```

### Coding Conventions

#### 1. **Dependency Injection**
Always use the container for service access:

```python
# ✅ Good
ldap_service = current_app.container.get("ldap_service")

# ❌ Bad
from app.services.ldap_service import ldap_service  # Global import
```

#### 2. **Model Patterns**
Extend appropriate base classes:

```python
# ✅ Good
from app.models.base import BaseModel, TimestampMixin

class MyModel(BaseModel, TimestampMixin):
    __tablename__ = "my_table"

    name = db.Column(db.String(255), nullable=False)

    def custom_method(self):
        self.update(name="new name")

# ❌ Bad - reimplementing base functionality
class MyModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Already in BaseModel
    created_at = db.Column(db.DateTime)  # Already in TimestampMixin
```

#### 3. **Service Patterns**
Implement interfaces and extend base classes:

```python
# ✅ Good
from app.interfaces.search_service import ISearchService
from app.services.base import BaseSearchService

class MySearchService(BaseSearchService, ISearchService):
    def __init__(self):
        super().__init__("my_service")

    def search_user(self, term: str) -> Optional[Dict[str, Any]]:
        # Implementation
        pass

# Register in container
container.register("my_service", lambda c: MySearchService())
```

#### 4. **Authentication & Authorization**
Always use decorators on routes:

```python
# ✅ Good
@blueprint.route("/my-route")
@auth_required
@require_role("editor")
def my_route():
    user_email = g.user
    ip_address = format_ip_info()
    # Route logic

# ❌ Bad - no authentication
@blueprint.route("/my-route")
def my_route():
    # Anyone can access
```

#### 5. **Error Handling**
Use decorators and proper logging:

```python
# ✅ Good
from app.utils.error_handler import handle_service_errors

@handle_service_errors(raise_errors=False)
def my_service_method(self):
    try:
        # Service logic
        result = risky_operation()
        return result
    except SpecificException as e:
        logger.error(f"Operation failed: {str(e)}", exc_info=True)
        audit_service.log_error(
            error_type="operation_error",
            message=str(e),
            user_email=g.user
        )
        raise

# ❌ Bad - swallowing errors
def my_service_method(self):
    try:
        return risky_operation()
    except:
        pass  # Silent failure
```

#### 6. **SQL Queries**
Avoid N+1 queries:

```python
# ✅ Good - bulk query
mapping_counts = db.session.query(
    JobRoleMapping.job_code_id,
    func.count(JobRoleMapping.id)
).group_by(JobRoleMapping.job_code_id).all()

# ❌ Bad - N+1 query
for job_code in job_codes:
    count = job_code.mappings.count()  # Separate query each iteration
```

#### 7. **Security**
Never hardcode secrets:

```python
# ✅ Good
api_key = config_get("api", "key")
secret = os.getenv("SECRET_KEY")

# ❌ Bad
api_key = "hardcoded-secret-key-12345"
```

Always escape user input in templates:

```html
<!-- ✅ Good -->
<script>
const data = {{ data|tojson|safe }};
const userInput = escapeHtml({{ user_input|tojson|safe }});
</script>

<!-- ❌ Bad -->
<script>
const data = {{ data|safe }};  // Potential XSS
</script>
```

### Documentation Standards

#### Code Comments
- Write self-documenting code (clear variable/function names)
- Add comments only where logic is complex or non-obvious
- Keep comments up-to-date with code changes
- Use docstrings for functions/classes

```python
# ✅ Good
def calculate_compliance_score(user_roles: List[str], expected_roles: List[str]) -> float:
    """
    Calculate compliance score based on role matching.

    Args:
        user_roles: List of actual roles the user has
        expected_roles: List of roles the user should have

    Returns:
        Compliance score from 0.0 (no match) to 1.0 (perfect match)
    """
    if not expected_roles:
        return 1.0

    matches = len(set(user_roles) & set(expected_roles))
    return matches / len(expected_roles)

# ❌ Bad
def calc(r1, r2):  # Unclear names, no docstring
    # Calculate score
    return len(set(r1) & set(r2)) / len(r2)
```

#### Markdown Documentation
- Use clear, descriptive headings
- Include code examples
- Add links to related documentation
- Keep table of contents updated

## Testing Guidelines

### Testing Strategy (When Implemented)

Currently, WhoDis does not have a test suite. When adding tests:

1. **Add pytest to requirements.txt**
   ```bash
   pip install pytest pytest-cov pytest-flask
   ```

2. **Test Structure**
   ```
   tests/
   ├── unit/
   │   ├── test_models.py
   │   ├── test_services.py
   │   └── test_utils.py
   ├── integration/
   │   ├── test_api.py
   │   └── test_database.py
   └── conftest.py
   ```

3. **Writing Tests**
   ```python
   # tests/unit/test_services.py
   import pytest
   from app.services.ldap_service import LDAPService

   def test_search_user_valid(mock_ldap):
       service = LDAPService()
       result = service.search_user("john.doe")

       assert result is not None
       assert result['email'] == 'john.doe@example.com'

   def test_search_user_not_found(mock_ldap):
       service = LDAPService()
       result = service.search_user("nonexistent")

       assert result is None
   ```

4. **Running Tests**
   ```bash
   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=app --cov-report=html

   # Run specific test file
   pytest tests/unit/test_services.py

   # Run specific test
   pytest tests/unit/test_services.py::test_search_user_valid
   ```

### Manual Testing Checklist

Before submitting a PR, manually test:

- [ ] Application starts without errors
- [ ] New features work as expected
- [ ] Existing features still work (regression testing)
- [ ] Error handling works correctly
- [ ] UI displays properly in different browsers
- [ ] Mobile responsive design (if UI changes)
- [ ] Database migrations apply cleanly
- [ ] Audit logs capture events correctly
- [ ] Security: No sensitive data exposed
- [ ] Performance: No significant slowdowns

## Pull Request Process

### Before Submitting

1. **Update Documentation**
   - Update CHANGELOG.md if significant change
   - Update relevant docs/ files
   - Add/update code comments and docstrings

2. **Run Quality Checks**
   ```bash
   ruff check --fix
   mypy app/ scripts/
   ```

3. **Test Thoroughly**
   - Manual testing of your changes
   - Test edge cases and error conditions
   - Verify no regressions in existing functionality

4. **Review Your Own Code**
   - Read through your diff on GitHub
   - Check for debugging code, console.logs, etc.
   - Ensure commit messages are clear

### PR Template

When creating a PR, include:

```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## Changes Made
- Bullet point list of specific changes
- Reference any related issues (#123)

## Testing
Describe testing performed:
- [ ] Manual testing completed
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated

## Checklist
- [ ] Code follows project style guidelines
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] No sensitive data exposed
- [ ] Linting passes (ruff check)
- [ ] Type checking passes (mypy)

## Screenshots (if applicable)
Add screenshots for UI changes
```

### Review Process

1. **Automated Checks**
   - GitHub will run automated checks
   - Fix any failing checks before requesting review

2. **Code Review**
   - At least one maintainer will review your PR
   - Address feedback and comments
   - Push additional commits to address review

3. **Approval and Merge**
   - Once approved, a maintainer will merge your PR
   - PR will be squashed and merged with a clean commit message
   - Your contribution will be credited in CHANGELOG.md

## Documentation

### When to Update Documentation

Update documentation when you:
- Add a new feature
- Change existing behavior
- Fix a bug that affects usage
- Modify APIs or interfaces
- Change configuration options
- Update dependencies

### Documentation Files to Update

| Change Type | Documentation to Update |
|-------------|------------------------|
| New feature | README.md, docs/architecture.md, CHANGELOG.md |
| Bug fix | CHANGELOG.md, docs/troubleshooting.md |
| Breaking change | CHANGELOG.md, README.md, CLAUDE.md |
| Security fix | SECURITY.md, CHANGELOG.md |
| New model/service | docs/architecture.md, CLAUDE.md |
| Database change | docs/database.md |
| Deployment change | docs/deployment.md |

## Questions and Support

### Getting Help

- **Documentation**: Check [docs/](docs/) directory first
- **Issues**: Search [existing issues](https://github.com/jslitzkerttcu/Who-Dis/issues)
- **Questions**: Open a GitHub issue with `question` label
- **Chat**: Contact maintainers via email (see SECURITY.md)

### Reporting Bugs

Use this template when reporting bugs:

```markdown
**Description**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What you expected to happen

**Environment**
- OS: [e.g., Ubuntu 20.04]
- Python version: [e.g., 3.10]
- PostgreSQL version: [e.g., 12.5]
- WhoDis version: [e.g., 2.1.1]

**Logs**
Relevant error logs or stack traces
```

### Feature Requests

Before requesting a feature:
1. Check [docs/PLANNING.md](docs/PLANNING.md) - it may already be planned
2. Search existing issues for similar requests
3. Open an issue with `enhancement` label if not found

## License and Attribution

By contributing to WhoDis, you agree that your contributions will be licensed under the same license as the project.

All contributors will be recognized in:
- Git commit history
- CHANGELOG.md release notes
- Future CONTRIBUTORS file (when created)

---

Thank you for contributing to WhoDis! 🎉

*For security-related contributions, please review [SECURITY.md](SECURITY.md) first.*
