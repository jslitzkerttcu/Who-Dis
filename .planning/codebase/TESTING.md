# Testing Patterns

**Analysis Date:** 2026-04-24

## Test Framework

**Status:** No test framework configured

**Current State:**
- No test files in application code (`app/` directory)
- No pytest, unittest, or vitest configuration
- No test runners in requirements.txt (though ruff and mypy are present)
- Script-based testing only: `scripts/debug/test_*.py` files are manual verification scripts, not automated tests

**What's Needed:**
- Add `pytest` to requirements.txt to enable testing
- No test configuration file exists yet (`pytest.ini`, `pyproject.toml`, etc.)
- No fixtures or factories currently implemented

**Recommendation:**
- When implementing test suite, use pytest (industry standard for Python)
- Add pytest configuration to `pyproject.toml` or `pytest.ini` in project root
- Follow patterns established in this codebase (type hints, error handling, mixins)

## Script-Based Testing (Current Approach)

**Location:** `scripts/debug/`

**Test Scripts:**
- `test_config_decryption.py`: Verifies encryption key and config access
- `test_locations_cache.py`: Tests Genesys cache functionality
- `check_genesys_cache.py`: Validates Genesys API connectivity
- `check_config_mapping.py`: Verifies configuration mappings
- `check_encrypted_status.py`: Checks encryption status
- `debug_config_values.py`: Prints configuration values for inspection
- `debug_missing_fields.py`: Identifies missing config fields

**Pattern:**
- Scripts import app context and run checks directly
- Used for manual verification and debugging, not automated regression testing
- Example: `scripts/debug/test_config_decryption.py` verifies that encryption works

**Run Method:**
```bash
python scripts/debug/test_config_decryption.py
python scripts/debug/test_locations_cache.py
```

## Testing Infrastructure Gaps

**Missing Components:**
1. **No Unit Test Suite** - Services and models untested
2. **No Integration Tests** - API integrations not verified
3. **No E2E Tests** - User workflows not tested
4. **No Fixtures** - No test data factories
5. **No Coverage Reporting** - No coverage configuration
6. **No Test Isolation** - No mock/patch patterns defined

**Fragile Areas (High Priority for Testing):**
- `app/services/search_orchestrator.py` (80 lines, coordinates multiple APIs)
- `app/services/genesys_service.py` (668 lines, complex token + search logic)
- `app/services/ldap_service.py` (652 lines, LDAP connection pooling)
- `app/blueprints/search/__init__.py` (2720 lines, main search route)
- `app/blueprints/admin/database.py` (2532 lines, admin database UI)

## Type Hints for Testing

**Type Coverage:**
- All service methods have type hints: `def search_user(self, search_term: str) -> Optional[Dict[str, Any]]`
- All models have type hints: `email: db.Column(db.String(255), nullable=False)`
- All interfaces define abstract methods with type hints

**Mypy Configuration:**
- Located: `mypy.ini`
- Run: `mypy app/ scripts/`
- Settings allow implicit optionals for SQLAlchemy models but require type hints otherwise

**Benefits for Testing:**
- Type hints make it clear what inputs/outputs tests should verify
- Mypy can catch some errors before tests are written
- Interfaces define contracts that implementations must follow

## Recommended Testing Structure (Future Implementation)

**Test Directory Organization:**
```
tests/
├── conftest.py              # Shared fixtures, test config
├── fixtures/
│   ├── database.py          # Database fixtures, cleanup
│   ├── models.py            # Model factory fixtures
│   └── mock_services.py     # Mock service instances
├── unit/
│   ├── models/
│   │   ├── test_user.py
│   │   └── test_api_token.py
│   ├── services/
│   │   ├── test_search_orchestrator.py
│   │   ├── test_ldap_service.py
│   │   └── test_genesys_service.py
│   └── middleware/
│       └── test_auth.py
├── integration/
│   ├── test_search_flow.py
│   └── test_admin_routes.py
└── e2e/
    └── test_user_workflows.py
```

## Mocking Strategy (Future Implementation)

**Framework:** Use `unittest.mock` (standard library) or `pytest-mock`

**Patterns to Implement:**

**Service Mocking:**
```python
# Example structure for future tests
from unittest.mock import Mock, patch, MagicMock

def test_search_with_mocked_ldap():
    """Test search orchestrator with mocked LDAP service."""
    with patch('app.services.ldap_service.LDAPService.search_user') as mock_ldap:
        mock_ldap.return_value = {'email': 'user@example.com', 'name': 'John Doe'}
        result = search_orchestrator.search('john')
        assert result['email'] == 'user@example.com'
```

**Database Mocking:**
```python
# Mock database transactions for unit tests
def test_user_creation():
    """Test user creation without hitting database."""
    with patch('app.database.db.session.add') as mock_add:
        user = User(email='test@example.com', role='viewer')
        mock_add.assert_called()
```

**API Request Mocking:**
```python
# Mock external API calls
def test_genesys_search_with_mocked_api():
    """Test Genesys service with mocked HTTP requests."""
    with patch('requests.request') as mock_request:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'users': [{'id': '123', 'name': 'John'}]}
        mock_request.return_value = mock_response
        
        service = GenesysService()
        result = service.search_user('john')
        assert result['id'] == '123'
```

**What to Mock:**
- External API calls (Genesys, Graph, LDAP)
- Database queries (when testing business logic in isolation)
- Configuration service (to test different config scenarios)
- Datetime (for testing expiration logic)

**What NOT to Mock:**
- Model save/delete operations (test with real database or use transactions)
- Decorator behavior (test actual auth flows)
- Core service orchestration logic (test full call chains)
- Error handling (test actual exception flows)

## Fixtures and Factories (Future Implementation)

**Test Data Pattern:**
```python
# Suggested factory pattern for models
from factory import Factory, Faker

class UserFactory(Factory):
    class Meta:
        model = User
    
    email = Faker('email')
    role = 'viewer'
    is_active = True

class ApiTokenFactory(Factory):
    class Meta:
        model = ApiToken
    
    service_name = 'genesys'
    access_token = Faker('sha256')
    expires_at = Faker('date_time_this_month')

# Usage in tests
def test_user_search():
    user = UserFactory(email='john@example.com')
    token = ApiTokenFactory(service_name='genesys')
    # Test logic
```

**Fixture Patterns:**
```python
# conftest.py - shared fixtures
@pytest.fixture
def app():
    """Create Flask test app with test database."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Create CLI runner for testing scripts."""
    return app.test_cli_runner()
```

**Location:**
- Core fixtures: `tests/conftest.py`
- Model factories: `tests/fixtures/models.py`
- Service mocks: `tests/fixtures/mock_services.py`

## Coverage

**Current Status:** Not tracked

**Setup (When Implementing Tests):**

**Installation:**
```bash
pip install pytest-cov
```

**Configuration:** Add to `pyproject.toml` or `pytest.ini`:
```ini
[tool:pytest]
addopts = --cov=app --cov-report=html --cov-report=term-missing
testpaths = tests
```

**Run Coverage:**
```bash
pytest --cov=app --cov-report=html tests/
# Opens htmlcov/index.html in browser
```

**Target:** 80% minimum coverage for:
- Services (`app/services/`)
- Models (`app/models/`)
- Middleware (`app/middleware/`)
- Blueprints (`app/blueprints/`)

**Areas to Prioritize:**
1. `app/services/search_orchestrator.py` - Core search coordination
2. `app/services/ldap_service.py` - LDAP connection + search
3. `app/models/base.py` - Base model functionality (mixin logic)
4. `app/middleware/auth.py` - Authentication flow
5. `app/blueprints/search/__init__.py` - Main search route

## Test Types

**Unit Tests (When Implemented):**
- Scope: Individual functions, methods, services in isolation
- Approach: Mock all external dependencies (APIs, database, config)
- Examples: Test `BaseSearchService._normalize_search_term()`, `User.get_by_email()`
- Location: `tests/unit/{component}/`

**Integration Tests (When Implemented):**
- Scope: Multiple services working together; real database
- Approach: Use test database, mock external APIs only
- Examples: Test full search flow through orchestrator; auth middleware → user provisioning
- Location: `tests/integration/`

**E2E Tests (Future):**
- Scope: Full user workflows through HTTP layer
- Approach: Use test Flask client; real database, mock external APIs
- Examples: User logs in → searches → views results
- Framework: Flask test client (not Selenium/Playwright unless UI testing needed)

**Script-Based Tests (Current):**
- Scope: Manual verification of setup and connectivity
- Location: `scripts/debug/test_*.py`
- Run: `python scripts/debug/test_config_decryption.py`

## Error Handling Testing

**Patterns to Test (When Implemented):**

**Decorator Behavior:**
```python
# Test @handle_errors decorator
def test_route_error_handling(client):
    """Verify route error is caught and logged."""
    with patch('app.utils.error_handler.logger') as mock_logger:
        response = client.get('/admin/invalid')
        assert response.status_code == 500
        mock_logger.error.assert_called()

def test_service_error_handling():
    """Verify @handle_service_errors logs and re-raises."""
    @handle_service_errors(raise_errors=True)
    def failing_method():
        raise ValueError("Test error")
    
    with pytest.raises(ValueError):
        failing_method()
```

**Specific Error Cases:**
- Invalid input (ValueError) → 400 response
- Permission denied (PermissionError) → 403 response
- Database errors (SQLAlchemyError) → 500 with generic message
- Unhandled exceptions → 500 with error_id tracking

## Async Testing

**Current Status:** Synchronous codebase only

**Background Tasks:**
- Token refresh uses `threading.Thread` (not async/await)
- Cache refresh uses threads
- No async/await patterns in code

**Testing Approach (If Needed):**
```python
# For thread-based operations
def test_token_refresh_thread():
    """Test that background token refresh service starts."""
    from app.services.token_refresh_service import token_refresh_service
    
    # Mock the service's start method
    with patch.object(token_refresh_service, 'start'):
        token_refresh_service.start()
        token_refresh_service.start.assert_called_once()
```

## Common Patterns

**Testing Service Search Methods:**
```python
# Pattern to follow when implementing tests
def test_ldap_search_returns_single_result():
    """Test LDAP search with one match."""
    service = LDAPService()
    with patch.object(service, '_make_ldap_query') as mock_query:
        mock_query.return_value = [{'cn': 'john.doe', 'mail': 'john@example.com'}]
        result = service.search_user('john')
        assert result['email'] == 'john@example.com'

def test_service_search_multiple_results():
    """Test service returns multiple_results flag when >1 match."""
    with patch('app.services.ldap_service.ldap3.Server'):
        service = LDAPService()
        with patch.object(service, '_make_ldap_query') as mock_query:
            mock_query.return_value = [
                {'cn': 'john.doe', 'mail': 'john@example.com'},
                {'cn': 'john.smith', 'mail': 'jsmith@example.com'}
            ]
            result = service.search_user('john')
            assert result['multiple_results'] == True
            assert len(result['results']) == 2

def test_service_search_no_results():
    """Test service returns None when no matches."""
    service = LDAPService()
    with patch.object(service, '_make_ldap_query') as mock_query:
        mock_query.return_value = []
        result = service.search_user('nonexistent')
        assert result is None
```

**Testing Model Methods:**
```python
# Model testing pattern
def test_user_get_by_email(app):
    """Test User.get_by_email() retrieves correct user."""
    with app.app_context():
        user = User.create_user('test@example.com', 'viewer')
        retrieved = User.get_by_email('test@example.com')
        assert retrieved.id == user.id
        assert retrieved.role == 'viewer'

def test_user_update_last_login(app):
    """Test last_login timestamp is updated."""
    with app.app_context():
        user = User.create_user('test@example.com')
        original_login = user.last_login
        
        user.update_last_login()
        
        assert user.last_login > original_login
        assert user.last_login.tzinfo is not None  # UTC timezone preserved
```

---

*Testing analysis: 2026-04-24*
