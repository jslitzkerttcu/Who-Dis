# Services API Reference

This document provides detailed API documentation for WhoDis service layer classes.

## Table of Contents
- [Base Service Classes](#base-service-classes)
- [Service Interfaces](#service-interfaces)
- [Core Services](#core-services)
- [Search Services](#search-services)
- [Cache Services](#cache-services)
- [Support Services](#support-services)

## Base Service Classes

### BaseConfigurableService

Base class for services that use configuration from the database.

**Location:** `app/services/base.py`

#### Constructor

```python
def __init__(self, config_prefix: str):
    """
    Args:
        config_prefix: Prefix for configuration keys (e.g., 'genesys', 'graph')
    """
```

#### Methods

##### _get_config()

```python
def _get_config(self, key: str, default: Any = None) -> Any:
    """
    Get configuration value with caching.

    Args:
        key: Configuration key (without prefix)
        default: Default value if not found

    Returns:
        Configuration value
    """
```

**Example:**
```python
class MyService(BaseConfigurableService):
    def __init__(self):
        super().__init__("myservice")

    def connect(self):
        host = self._get_config("host", "localhost")
        port = self._get_config("port", 5432)
```

##### _clear_config_cache()

```python
def _clear_config_cache(self):
    """Clear the configuration cache to force reload."""
```

Use when configuration has been updated and needs to be reloaded.

##### _load_config()

```python
def _load_config(self):
    """Load configuration - can be overridden by subclasses."""
```

Override this method to preload configuration in bulk.

---

### BaseAPIService

Base class for API-based services with HTTP functionality.

**Extends:** `BaseConfigurableService`

**Location:** `app/services/base.py`

#### Properties

##### timeout

```python
@property
def timeout(self) -> int:
    """Get API timeout in seconds. Default: 15"""
```

##### base_url

```python
@property
def base_url(self) -> str:
    """Get base URL for API from configuration."""
```

#### Methods

##### _get_headers()

```python
def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
    """
    Get standard headers for API requests.

    Args:
        token: Optional bearer token

    Returns:
        Headers dictionary with Content-Type, Accept, and Authorization (if token)
    """
```

##### _make_request()

```python
def _make_request(
    self, method: str, url: str, token: Optional[str] = None, **kwargs
) -> requests.Response:
    """
    Make HTTP request with standard error handling.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        url: Full URL to request
        token: Optional bearer token
        **kwargs: Additional arguments for requests library

    Returns:
        Response object

    Raises:
        TimeoutError: If request times out
        ConnectionError: If connection fails
        requests.HTTPError: If response status is not successful
    """
```

**Example:**
```python
class MyAPIService(BaseAPIService):
    def __init__(self):
        super().__init__("myapi")

    def get_user(self, user_id: str):
        url = f"{self.base_url}/users/{user_id}"
        response = self._make_request("GET", url, token=self.get_token())
        return response.json()
```

##### _handle_response()

```python
def _handle_response(self, response: requests.Response) -> Any:
    """
    Handle API response and extract JSON data.

    Args:
        response: HTTP response object

    Returns:
        Parsed JSON data or None if error
    """
```

##### test_connection()

```python
@abstractmethod
def test_connection(self) -> bool:
    """
    Test service connection. Must be implemented by subclasses.

    Returns:
        True if connection successful, False otherwise
    """
```

---

### BaseTokenService

Base class for services with OAuth2 token management.

**Extends:** `BaseAPIService`

**Location:** `app/services/base.py`

#### Constructor

```python
def __init__(
    self,
    config_prefix: str,
    token_service_name: str,
    cache_repository: Optional[ICacheRepository] = None,
):
    """
    Args:
        config_prefix: Prefix for configuration keys
        token_service_name: Name for token storage (e.g., 'genesys', 'microsoft_graph')
        cache_repository: Repository for token caching (optional, uses default if None)
    """
```

#### Methods

##### get_access_token()

```python
def get_access_token(self) -> Optional[str]:
    """
    Get access token, using cache if available.

    Returns:
        Access token or None if unable to obtain
    """
```

**Flow:**
1. Check cache for valid token
2. If cached and not expired, return it
3. Otherwise, fetch new token via `_fetch_new_token()`
4. Cache new token and return it

##### _fetch_new_token()

```python
@abstractmethod
def _fetch_new_token(self) -> Optional[str]:
    """
    Fetch a new access token from the service.

    Must be implemented by subclasses to handle service-specific auth.
    Should call _store_token() to cache the token.

    Returns:
        Access token or None if unable to obtain
    """
```

##### refresh_token_if_needed()

```python
def refresh_token_if_needed(self) -> bool:
    """
    Check and refresh token if needed.

    Returns:
        True if token is valid (either existing or newly fetched)
    """
```

**Example:**
```python
class MyTokenService(BaseTokenService):
    def __init__(self):
        super().__init__(
            config_prefix="myapi",
            token_service_name="my_service"
        )

    def _fetch_new_token(self) -> Optional[str]:
        client_id = self._get_config("client_id")
        client_secret = self._get_config("client_secret")

        # OAuth2 client credentials flow
        response = self._make_request(
            "POST",
            f"{self.base_url}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret
            }
        )

        data = response.json()
        access_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)

        # Cache the token
        self._store_token(access_token, expires_in)

        return access_token
```

---

### BaseSearchService

Base class for services with user search functionality.

**Extends:** `BaseConfigurableService`

**Location:** `app/services/base.py`

#### Methods

##### search_user()

```python
@abstractmethod
def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
    """
    Search for a user. Must be implemented by subclasses.

    Args:
        search_term: Term to search for (email, username, etc.)

    Returns:
        User data dictionary or None if not found
        If multiple results, returns dict with 'multiple_results' = True
    """
```

##### _normalize_search_term()

```python
def _normalize_search_term(self, search_term: str) -> List[str]:
    """
    Normalize search term and generate variations.

    Args:
        search_term: The search term to normalize

    Returns:
        List of search term variations

    Example:
        Input: "john.doe@example.com"
        Output: ["john.doe@example.com", "john.doe"]
    """
```

##### _format_multiple_results()

```python
def _format_multiple_results(
    self, results: List[Dict[str, Any]], total: Optional[int] = None
) -> Dict[str, Any]:
    """
    Format multiple search results in standard format.

    Args:
        results: List of result dictionaries
        total: Total number of results (if different from len(results))

    Returns:
        Formatted results dictionary:
        {
            "multiple_results": True,
            "results": [...],
            "total": n
        }
    """
```

---

### BaseCacheService

Base class for services with database caching functionality.

**Extends:** `BaseConfigurableService`

**Location:** `app/services/base.py`

#### Properties

##### cache_timeout

```python
@property
def cache_timeout(self) -> int:
    """Get cache timeout in seconds. Default: 30"""
```

##### cache_refresh_period

```python
@property
def cache_refresh_period(self) -> int:
    """Get cache refresh period in seconds. Default: 21600 (6 hours)"""
```

#### Methods

##### needs_refresh()

```python
def needs_refresh(self, last_update: datetime) -> bool:
    """
    Check if cache needs refresh based on last update time.

    Args:
        last_update: Last update timestamp

    Returns:
        True if cache needs refresh (older than refresh_period)
    """
```

##### refresh_cache()

```python
@abstractmethod
def refresh_cache(self) -> Dict[str, int]:
    """
    Refresh cache data. Must be implemented by subclasses.

    Returns:
        Dictionary with refresh statistics (e.g., {'items': 100})
    """
```

**Example:**
```python
class MyCache Service(BaseCacheService):
    def __init__(self):
        super().__init__("mycache")

    def refresh_cache(self) -> Dict[str, int]:
        # Fetch data from API
        data = self.fetch_all_items()

        # Store in database cache
        count = 0
        for item in data:
            MyCacheModel.upsert(item)
            count += 1

        return {"items": count}
```

---

### BaseAPITokenService

Composite base class for API services with token management and search.

**Extends:** `BaseTokenService`, `BaseSearchService`

**Location:** `app/services/base.py`

Combines functionality from both base classes. Use when creating a service that:
- Makes API calls requiring OAuth2 tokens
- Implements user search functionality

**Example:**
```python
class GenesysCloudService(BaseAPITokenService, ISearchService):
    def __init__(self):
        super().__init__(
            config_prefix="genesys",
            token_service_name="genesys_cloud"
        )

    def _fetch_new_token(self) -> Optional[str]:
        # OAuth2 implementation
        pass

    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        token = self.get_access_token()
        # Search implementation using token
        pass

    def test_connection(self) -> bool:
        # Test implementation
        pass

    @property
    def service_name(self) -> str:
        return "Genesys Cloud"
```

---

## Service Interfaces

### ISearchService

Interface for user search services.

**Location:** `app/interfaces/search_service.py`

```python
class ISearchService(ABC):
    @abstractmethod
    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        """Search for a user by email, username, or other identifier."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the service is available and properly configured."""
        pass

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Get the name of this search service."""
        pass
```

---

### IAuditService

Interface for audit logging services.

**Location:** `app/interfaces/audit_service.py`

```python
class IAuditService(ABC):
    @abstractmethod
    def log_search(self, user_email: str, search_query: str, **kwargs):
        """Log a search event."""
        pass

    @abstractmethod
    def log_access_attempt(self, user_email: str, resource: str, **kwargs):
        """Log an access attempt (denied or granted)."""
        pass

    @abstractmethod
    def log_admin_action(self, user_email: str, action: str, **kwargs):
        """Log an administrative action."""
        pass

    @abstractmethod
    def log_error(self, error_type: str, message: str, **kwargs):
        """Log an error."""
        pass
```

---

### ICacheRepository

Interface for cache storage repositories.

**Location:** `app/interfaces/cache_repository.py`

```python
class ICacheRepository(ABC):
    @abstractmethod
    def get_cached_search(self, search_query: str) -> Optional[Dict[str, Any]]:
        """Get cached search result."""
        pass

    @abstractmethod
    def cache_search_result(self, search_query: str, result_data: Dict[str, Any], ttl_seconds: int):
        """Cache a search result."""
        pass

    @abstractmethod
    def get_token(self, service_name: str) -> Optional[str]:
        """Get cached API token."""
        pass

    @abstractmethod
    def cache_api_token(self, service_name: str, access_token: str, expires_in_seconds: int):
        """Cache an API token."""
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Remove expired cache entries. Returns count of removed items."""
        pass
```

---

## Core Services

### LDAPService

Service for Active Directory/LDAP integration.

**Location:** `app/services/ldap_service.py`

**Implements:** `BaseSearchService`, `ISearchService`

#### Methods

##### search_user()

```python
def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
    """
    Search for a user in LDAP/Active Directory.

    Searches across multiple attributes:
    - mail (email)
    - displayName
    - givenName (first name)
    - sn (surname)
    - sAMAccountName
    - userPrincipalName

    Args:
        search_term: Email, name, or username to search for

    Returns:
        User dictionary with LDAP attributes or None
        Multiple results returned as {"multiple_results": True, "results": [...]}
    """
```

##### test_connection()

```python
def test_connection(self) -> bool:
    """
    Test LDAP connection and credentials.

    Returns:
        True if connection successful and bind works
    """
```

**Example:**
```python
ldap_service = current_app.container.get("ldap_service")

# Search by email
result = ldap_service.search_user("john.doe@example.com")

# Search by name
result = ldap_service.search_user("John Doe")

# Result structure
if result:
    print(f"Name: {result['displayName']}")
    print(f"Email: {result['mail']}")
    print(f"Title: {result['title']}")
    print(f"Department: {result['department']}")
```

---

### GenesysCloudService

Service for Genesys Cloud API integration.

**Location:** `app/services/genesys_service.py`

**Implements:** `BaseAPITokenService`, `ISearchService`

#### Methods

##### search_user()

```python
def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
    """
    Search for a user in Genesys Cloud.

    Searches by name, email, or username.

    Args:
        search_term: Name, email, or username to search for

    Returns:
        User dictionary with Genesys data including:
        - Basic info (name, email, username)
        - Skills, queues, groups
        - Contact information
        - Division, location
    """
```

##### get_user_skills()

```python
def get_user_skills(self, user_id: str) -> List[Dict[str, Any]]:
    """
    Get skills for a Genesys user.

    Args:
        user_id: Genesys user ID

    Returns:
        List of skill dictionaries
    """
```

##### get_user_queues()

```python
def get_user_queues(self, user_id: str) -> List[Dict[str, Any]]:
    """
    Get queues for a Genesys user.

    Args:
        user_id: Genesys user ID

    Returns:
        List of queue dictionaries
    """
```

**Example:**
```python
genesys_service = current_app.container.get("genesys_service")

result = genesys_service.search_user("john.doe")

if result:
    print(f"Agent: {result['name']}")
    print(f"Queues: {len(result['queues'])}")
    print(f"Skills: {len(result['skills'])}")
```

---

### GraphService

Service for Microsoft Graph API integration.

**Location:** `app/services/graph_service.py`

**Implements:** `BaseAPITokenService`, `ISearchService`

#### Methods

##### search_user()

```python
def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
    """
    Search for a user via Microsoft Graph API.

    Enhanced profile data beyond LDAP:
    - hire Date
    - Password policies
    - Additional attributes

    Args:
        search_term: Email or user principal name

    Returns:
        User dictionary with enhanced Graph data
    """
```

##### get_user_photo()

```python
def get_user_photo(self, user_id: str) -> Optional[str]:
    """
    Get user's profile photo from Microsoft Graph.

    Args:
        user_id: User ID or UPN

    Returns:
        Base64-encoded photo data or None
    """
```

**Example:**
```python
graph_service = current_app.container.get("graph_service")

result = graph_service.search_user("john.doe@example.com")
photo = graph_service.get_user_photo(result['id'])

if photo:
    # photo is base64-encoded image data
    img_tag = f'<img src="data:image/jpeg;base64,{photo}" />'
```

---

## Search Services

### SearchOrchestrator

Orchestrates concurrent searches across multiple services.

**Location:** `app/services/search_orchestrator.py`

#### Methods

##### search()

```python
def search(self, search_term: str) -> Dict[str, Any]:
    """
    Execute concurrent search across all enabled services.

    Services searched:
    - LDAP (if enabled)
    - Microsoft Graph (if enabled)
    - Genesys Cloud (if enabled)

    Args:
        search_term: Search query

    Returns:
        Combined results dictionary:
        {
            "ldap": {...},
            "graph": {...},
            "genesys": {...},
            "matched_user": {...},  # If auto-matched
            "multiple_results": True/False
        }
    """
```

**Features:**
- Executes searches concurrently using ThreadPoolExecutor
- Respects service timeout settings
- Automatically matches users across services
- Merges data from LDAP and Graph
- Returns combined results with source attribution

**Example:**
```python
search_orchestrator = current_app.container.get("search_orchestrator")

result = search_orchestrator.search("john.doe")

# Check if auto-matched
if "matched_user" in result:
    user = result["matched_user"]
    print(f"Found: {user['displayName']}")

# Check individual services
if result.get("ldap"):
    print("Found in LDAP")
if result.get("genesys"):
    print("Found in Genesys")
```

---

### ResultMerger

Merges search results from multiple sources.

**Location:** `app/services/result_merger.py`

#### Methods

##### merge_ldap_and_graph()

```python
def merge_ldap_and_graph(
    ldap_data: Dict[str, Any],
    graph_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge LDAP and Microsoft Graph data.

    Priority: Graph data takes precedence for enhanced fields

    Args:
        ldap_data: Data from LDAP
        graph_data: Data from Microsoft Graph

    Returns:
        Merged dictionary with best data from both sources
    """
```

---

### SearchEnhancer

Enhances search results with additional data.

**Location:** `app/services/search_enhancer.py`

#### Methods

##### enhance_with_employee_profile()

```python
def enhance_with_employee_profile(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance user data with employee profile information.

    Adds:
    - Photo from employee_profiles table
    - Data warehouse information
    - Keystone job code data

    Args:
        user_data: User dictionary from search

    Returns:
        Enhanced user dictionary
    """
```

---

## Cache Services

### GenesisCacheDB

Database caching service for Genesys data.

**Location:** `app/services/genesys_cache_db.py`

**Implements:** `BaseCacheService`

#### Methods

##### refresh_cache()

```python
def refresh_cache(self) -> Dict[str, int]:
    """
    Refresh Genesys cache (groups, skills, locations).

    Fetches from Genesys API and stores in PostgreSQL.

    Returns:
        Statistics dictionary:
        {
            "groups": 50,
            "skills": 120,
            "locations": 10
        }
    """
```

##### get_cached_groups()

```python
def get_cached_groups(self) -> List[Dict[str, Any]]:
    """Get all cached Genesys groups."""
```

##### get_cached_skills()

```python
def get_cached_skills(self) -> List[Dict[str, Any]]:
    """Get all cached Genesys skills."""
```

##### get_cached_locations()

```python
def get_cached_locations(self) -> List[Dict[str, Any]]:
    """Get all cached Genesys locations."""
```

---

## Support Services

### AuditServicePostgres

PostgreSQL-based audit logging service.

**Location:** `app/services/audit_service_postgres.py`

**Implements:** `IAuditService`

#### Methods

##### log_search()

```python
def log_search(
    self,
    user_email: str,
    search_query: str,
    results_count: int = 0,
    services_used: Optional[List[str]] = None,
    **kwargs
):
    """
    Log a search event to audit_log table.

    Args:
        user_email: Email of user performing search
        search_query: The search term used
        results_count: Number of results found
        services_used: List of services that returned results
        **kwargs: Additional metadata
    """
```

##### log_admin_action()

```python
def log_admin_action(
    self,
    user_email: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    **kwargs
):
    """
    Log an administrative action.

    Args:
        user_email: Admin performing action
        action: Action type (e.g., "user_created", "config_updated")
        details: Action details dictionary
        **kwargs: Additional metadata
    """
```

##### log_error()

```python
def log_error(
    self,
    error_type: str,
    message: str,
    stack_trace: Optional[str] = None,
    **kwargs
):
    """
    Log an error to error_log table.

    Args:
        error_type: Type of error
        message: Error message
        stack_trace: Optional stack trace
        **kwargs: Additional context
    """
```

---

### ConfigurationService

Service for managing encrypted configuration.

**Location:** `app/services/configuration_service.py`

#### Functions

##### config_get()

```python
def config_get(key: str, default: Any = None) -> Any:
    """
    Get configuration value from database.

    Handles automatic decryption of encrypted values.

    Args:
        key: Configuration key in dot notation (e.g., "ldap.host")
        default: Default value if key not found

    Returns:
        Configuration value (decrypted if encrypted)
    """
```

**Example:**
```python
from app.services.configuration_service import config_get

ldap_host = config_get("ldap.host", "ldap.example.com")
client_secret = config_get("genesys.client_secret")  # Auto-decrypted
```

##### config_set()

```python
def config_set(key: str, value: Any, encrypt: bool = None):
    """
    Set configuration value in database.

    Handles automatic encryption for sensitive values.

    Args:
        key: Configuration key in dot notation
        value: Value to store
        encrypt: Force encryption (None = auto-detect based on key name)
    """
```

**Example:**
```python
from app.services.configuration_service import config_set

# Auto-encrypts based on key name
config_set("genesys.client_secret", "new-secret-value")

# Force encryption
config_set("custom.api_key", "value", encrypt=True)

# Plain text
config_set("ldap.host", "newldap.example.com", encrypt=False)
```

---

### TokenRefreshService

Background service for automatic token refresh.

**Location:** `app/services/token_refresh_service.py`

#### Methods

##### start()

```python
def start(self):
    """Start background token refresh service in separate thread."""
```

##### stop()

```python
def stop(self):
    """Stop background token refresh service."""
```

**Features:**
- Checks tokens every 5 minutes
- Auto-refreshes tokens expiring within 10 minutes
- Runs in background thread
- Logs all refresh attempts

**Automatic Startup:** Service starts automatically with Flask application.

---

### EncryptionService

Service for encrypting/decrypting sensitive configuration values.

**Location:** `app/services/encryption_service.py`

#### Functions

##### encrypt_value()

```python
def encrypt_value(value: str) -> bytes:
    """
    Encrypt a string value using Fernet encryption.

    Args:
        value: Plain text value to encrypt

    Returns:
        Encrypted bytes
    """
```

##### decrypt_value()

```python
def decrypt_value(encrypted_value: Union[bytes, memoryview]) -> str:
    """
    Decrypt an encrypted value.

    Args:
        encrypted_value: Encrypted bytes (or memoryview from PostgreSQL BYTEA)

    Returns:
        Decrypted plain text string
    """
```

**Note:** Uses `WHODIS_ENCRYPTION_KEY` from environment and installation-specific salt file.

---

*Last Updated: December 29, 2025*
