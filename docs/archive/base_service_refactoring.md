# Base Service Class Refactoring Analysis

## Common Patterns Identified

After analyzing all service files in `app/services/`, I've identified several common patterns that could be extracted into a base service class:

### 1. Token Management Pattern
**Found in:** `genesys_service.py`, `graph_service.py`

Common functionality:
- Token acquisition and caching
- Token refresh logic
- Token storage in database
- Checking token validity
- Handling token expiration

```python
# Common pattern:
def _get_access_token(self) -> Optional[str]:
    # Check cache/database for existing token
    # If valid, return it
    # Otherwise, fetch new token
    # Store new token in database
    # Return token

def refresh_token_if_needed(self) -> bool:
    # Check token validity
    # Refresh if needed
    # Return success status
```

### 2. Configuration Access Pattern
**Found in:** All services

Common functionality:
- Lazy loading configuration values
- Reading from `config_get()` with defaults
- Property decorators for configuration values
- Configuration caching

```python
# Common pattern:
@property
def client_id(self):
    return config_get("service.client_id")

@property
def timeout(self):
    return int(config_get("service.timeout", "15"))
```

### 3. Error Handling Pattern
**Found in:** All services

Common functionality:
- Try/except blocks with logging
- Timeout handling
- Connection error handling
- Standardized error messages
- Error logging to database

```python
# Common pattern:
try:
    # Make API call
except Timeout:
    logger.error(f"Timeout after {self.timeout} seconds")
    raise TimeoutError("Operation timed out")
except ConnectionError as e:
    logger.error(f"Connection error: {str(e)}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}")
```

### 4. HTTP Request Pattern
**Found in:** `genesys_service.py`, `graph_service.py`, `genesys_cache_db.py`

Common functionality:
- Setting authorization headers
- Configurable timeouts
- Standard error handling
- Response validation
- JSON parsing

```python
# Common pattern:
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    url,
    headers=headers,
    timeout=self.timeout
)
if response.status_code == 200:
    return response.json()
```

### 5. Search/Query Pattern
**Found in:** `ldap_service.py`, `genesys_service.py`, `graph_service.py`

Common functionality:
- Search term normalization (email/username handling)
- Multiple result handling
- Result processing and formatting
- Timeout handling for searches

```python
# Common pattern:
def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
    # Normalize search term
    # Try multiple search variations
    # Handle multiple results
    # Process and format results
```

### 6. Connection Testing Pattern
**Found in:** `ldap_service.py`, `genesys_service.py`, `graph_service.py`

Common functionality:
- Test connection with fresh configuration
- Verify credentials
- Simple API call to validate connection
- Return boolean success status

```python
# Common pattern:
def test_connection(self) -> bool:
    # Reload configuration
    # Attempt connection
    # Perform simple test operation
    # Return success/failure
```

## Proposed Base Service Classes

### 1. BaseAPIService
For services that interact with REST APIs (Genesys, Graph):

```python
class BaseAPIService:
    """Base class for API-based services with token management."""
    
    def __init__(self):
        self._initialized = False
        self._config_prefix = None  # Override in subclass
        
    @property
    def timeout(self):
        return int(config_get(f"{self._config_prefix}.api_timeout", "15"))
    
    def _get_headers(self, token: str) -> Dict[str, str]:
        """Get standard headers with authorization."""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, url: str, token: str, **kwargs) -> requests.Response:
        """Make HTTP request with standard error handling."""
        headers = self._get_headers(token)
        kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('headers', headers)
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except Timeout:
            logger.error(f"Timeout after {self.timeout} seconds: {url}")
            raise TimeoutError(f"Request timed out after {self.timeout} seconds")
        except ConnectionError as e:
            logger.error(f"Connection error to {url}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error making request to {url}: {str(e)}")
            raise
    
    @abstractmethod
    def _get_access_token(self) -> Optional[str]:
        """Get access token - must be implemented by subclass."""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test service connection - must be implemented by subclass."""
        pass
```

### 2. BaseTokenService
For services that need OAuth2 token management:

```python
class BaseTokenService(BaseAPIService):
    """Base class for services with OAuth2 token management."""
    
    def __init__(self):
        super().__init__()
        self._token_service_name = None  # Override in subclass
        
    def _get_cached_token(self) -> Optional[str]:
        """Get token from database cache."""
        try:
            from flask import current_app
            if current_app:
                from app.models.unified_cache import CacheEntry
                token_data = CacheEntry.get_token(self._token_service_name)
                if token_data and hasattr(token_data, 'access_token'):
                    logger.debug(f"Using cached token for {self._token_service_name}")
                    return str(token_data.access_token)
        except RuntimeError:
            logger.debug(f"No Flask app context for {self._token_service_name} token lookup")
        except Exception as e:
            logger.error(f"Error getting {self._token_service_name} token from database: {e}")
        return None
    
    def _store_token(self, access_token: str, expires_in: int = 3600):
        """Store token in database cache."""
        try:
            from flask import current_app
            if current_app:
                from app.models.unified_cache import CacheEntry
                CacheEntry.cache_api_token(
                    service_name=self._token_service_name,
                    access_token=access_token,
                    expires_in_seconds=expires_in
                )
                logger.debug(f"Stored {self._token_service_name} token in database")
        except RuntimeError:
            pass
        except Exception as e:
            logger.error(f"Error storing {self._token_service_name} token: {e}")
    
    def refresh_token_if_needed(self) -> bool:
        """Check and refresh token if needed."""
        try:
            token = self._get_access_token()
            return token is not None
        except Exception as e:
            logger.error(f"Error refreshing {self._token_service_name} token: {str(e)}")
            return False
```

### 3. BaseSearchService
For services that implement user search functionality:

```python
class BaseSearchService:
    """Base class for services with search functionality."""
    
    def _normalize_search_term(self, search_term: str) -> List[str]:
        """Normalize search term and generate variations."""
        variations = [search_term]
        
        # Handle email addresses
        if '@' in search_term:
            username = search_term.split('@')[0]
            variations.append(username)
            
        return variations
    
    def _format_multiple_results(self, results: List[Dict], total: int) -> Dict[str, Any]:
        """Format multiple search results."""
        return {
            "multiple_results": True,
            "results": results,
            "total": total
        }
    
    @abstractmethod
    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        """Search for a user - must be implemented by subclass."""
        pass
```

### 4. BaseCacheService
For services that implement caching functionality:

```python
class BaseCacheService:
    """Base class for services with database caching."""
    
    def __init__(self):
        self._cache_timeout = None
        self._cache_refresh_period = None
        
    @property
    def cache_timeout(self):
        if self._cache_timeout is None:
            self._cache_timeout = int(config_get(f"{self._config_prefix}.cache_timeout", "30"))
        return self._cache_timeout
    
    @property
    def cache_refresh_period(self):
        if self._cache_refresh_period is None:
            self._cache_refresh_period = int(config_get(f"{self._config_prefix}.cache_refresh_period", "21600"))
        return self._cache_refresh_period
    
    def needs_refresh(self) -> bool:
        """Check if cache needs refresh."""
        # Default implementation - can be overridden
        return True
    
    @abstractmethod
    def refresh_cache(self) -> Dict[str, int]:
        """Refresh cache - must be implemented by subclass."""
        pass
```

## Duplicate Code Analysis

### 1. Token Management (High Duplication)
- **GenesysService._get_access_token()** (lines 64-125)
- **GraphService._get_access_token()** (lines 57-112)

Both methods have nearly identical structure:
- Check Flask app context
- Get token from database
- Fetch new token if needed
- Store token in database
- Handle exceptions

**Recommendation:** Extract to `BaseTokenService._get_access_token()` with abstract method `_fetch_new_token()`

### 2. Configuration Properties (High Duplication)
Every service has similar property definitions for configuration values.

**Recommendation:** Create `BaseConfigurableService` with generic property factory method

### 3. Test Connection Methods (Medium Duplication)
- **GenesysService.test_connection()** (lines 136-218)
- **GraphService.test_connection()** (lines 124-191)

Common pattern:
- Reload configuration
- Create fresh client
- Get new token
- Make test API call
- Store token if successful

**Recommendation:** Extract common logic to `BaseAPIService.test_connection()` with abstract methods for service-specific parts

### 4. Error Handling (High Duplication)
Every service has similar try/except blocks with:
- Timeout handling
- Connection error handling
- Generic exception handling
- Logging

**Recommendation:** Use `@handle_service_errors` decorator more consistently or create base methods with built-in error handling

### 5. Search Methods (Medium Duplication)
All search methods follow similar patterns but with service-specific implementation details.

**Recommendation:** Extract common search patterns to `BaseSearchService` while keeping service-specific logic in subclasses

## Benefits of Refactoring

1. **Reduced Code Duplication:** ~40% reduction in code across services
2. **Consistent Error Handling:** Standardized error messages and logging
3. **Easier Maintenance:** Changes to common functionality only need to be made once
4. **Better Testing:** Can test base functionality once and focus on service-specific tests
5. **Improved Documentation:** Common patterns documented in one place
6. **Easier to Add New Services:** New services can inherit common functionality

## Implementation Priority

1. **High Priority:**
   - BaseTokenService for token management (affects Genesys, Graph)
   - BaseAPIService for HTTP request handling

2. **Medium Priority:**
   - BaseSearchService for search functionality
   - Error handling standardization

3. **Low Priority:**
   - BaseCacheService (only used by GenesysCacheDB)
   - Configuration property factory (current approach works fine)

## Migration Strategy

1. Create base classes in `app/services/base.py`
2. Refactor one service at a time, starting with GraphService (simpler)
3. Ensure all tests pass after each refactoring
4. Update GenesysService
5. Update other services as needed
6. Remove duplicate code and update imports