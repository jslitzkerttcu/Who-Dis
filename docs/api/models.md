# Models API Reference

This document provides detailed API documentation for WhoDis database models.

## Table of Contents
- [Base Model Classes](#base-model-classes)
- [Model Mixins](#model-mixins)
- [Core Models](#core-models)
- [Cache Models](#cache-models)
- [Audit Models](#audit-models)
- [Job Role Compliance Models](#job-role-compliance-models)
- [Utility Functions](#utility-functions)

## Base Model Classes

### BaseModel

Base class for all database models with common CRUD operations.

**Location:** `app/models/base.py`

**Extends:** `db.Model`, `SerializableMixin`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key (auto-increment) |

#### Class Methods

##### get_by_id()

```python
@classmethod
def get_by_id(cls, id_value):
    """
    Get record by ID.

    Args:
        id_value: ID to search for

    Returns:
        Model instance or None
    """
```

**Example:**
```python
user = User.get_by_id(123)
if user:
    print(user.email)
```

##### get_or_create()

```python
@classmethod
def get_or_create(cls, **kwargs):
    """
    Get existing record or create new one.

    Args:
        **kwargs: Field values to filter by

    Returns:
        Tuple of (instance, created) where created is True if new record
    """
```

**Example:**
```python
user, created = User.get_or_create(email="admin@example.com")
if created:
    user.role = "admin"
    user.save()
```

#### Instance Methods

##### save()

```python
def save(self, commit=True):
    """
    Save the current instance.

    Args:
        commit: Whether to commit immediately (default True)

    Returns:
        The saved instance

    Raises:
        Exception: If save fails (rolls back transaction)
    """
```

**Example:**
```python
user = User(email="new@example.com", role="viewer")
user.save()  # Commits immediately

# Batch operations
user1.save(commit=False)
user2.save(commit=False)
db.session.commit()  # Commit all at once
```

##### delete()

```python
def delete(self, commit=True):
    """
    Delete the current instance.

    Args:
        commit: Whether to commit immediately (default True)
    """
```

**Example:**
```python
user = User.get_by_id(123)
user.delete()  # Removed from database
```

##### update()

```python
def update(self, commit=True, **kwargs):
    """
    Update instance with provided values.

    Args:
        commit: Whether to commit immediately (default True)
        **kwargs: Field values to update

    Returns:
        The updated instance
    """
```

**Example:**
```python
user = User.get_by_id(123)
user.update(role="admin", commit=True)
```

---

### AuditableModel

Base model for audit logs and tracking.

**Location:** `app/models/base.py`

**Extends:** `BaseModel`, `TimestampMixin`, `UserTrackingMixin`, `JSONDataMixin`

**Use For:** Audit logs, access attempts, error logs

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `created_at` | DateTime(TZ) | When created (indexed) |
| `updated_at` | DateTime(TZ) | Last update |
| `user_email` | String(255) | User email (indexed) |
| `user_agent` | Text | Browser/client info |
| `ip_address` | String(45) | IP address (indexed) |
| `session_id` | String(255) | Session ID (indexed) |
| `success` | Boolean | Operation success flag (indexed) |
| `message` | Text | Event message |
| `additional_data` | JSONB | Extra JSON data |

**Example:**
```python
from app.models.audit import AuditLog

log = AuditLog(
    event_type="search",
    user_email="user@example.com",
    ip_address="192.168.1.100",
    message="Searched for john.doe",
    success=True
)
log.set_data("results_count", 1)
log.save()
```

---

### CacheableModel

Base model for cached entities with expiration.

**Location:** `app/models/base.py`

**Extends:** `BaseModel`, `TimestampMixin`, `ExpirableMixin`

**Use For:** Search cache, API tokens, temporary data

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `created_at` | DateTime(TZ) | When created (indexed) |
| `updated_at` | DateTime(TZ) | Last update |
| `expires_at` | DateTime(TZ) | Expiration time (indexed) |

#### Class Methods

##### get_valid_cache()

```python
@classmethod
def get_valid_cache(cls, **filters):
    """
    Get non-expired cache entries matching filters.

    Args:
        **filters: Field filters (e.g., search_query="john")

    Returns:
        List of non-expired cache entries
    """
```

**Example:**
```python
valid_caches = SearchCache.get_valid_cache(search_query="john.doe")
if valid_caches:
    cached_result = valid_caches[0].result_data
```

##### cleanup_and_get_stats()

```python
@classmethod
def cleanup_and_get_stats(cls):
    """
    Cleanup expired entries and return statistics.

    Returns:
        Dictionary with counts:
        {
            "total": 100,
            "expired_removed": 20,
            "valid_remaining": 80
        }
    """
```

---

### ServiceDataModel

Base model for external service data (Genesys, etc.).

**Location:** `app/models/base.py`

**Extends:** `BaseModel`, `TimestampMixin`, `JSONDataMixin`

**Use For:** Genesys groups, skills, locations; data warehouse data

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `created_at` | DateTime(TZ) | When created (indexed) |
| `updated_at` | DateTime(TZ) | Last update |
| `service_id` | String(255) | External service ID (indexed) |
| `service_name` | String(100) | Service name (indexed) |
| `raw_data` | JSONB | Complete API response |
| `is_active` | Boolean | Active status (indexed) |
| `additional_data` | JSONB | Extra processed data |

#### Instance Methods

##### update_from_service()

```python
def update_from_service(self, data: Dict[str, Any], commit=True):
    """
    Update model with fresh data from external service.

    Automatically extracts common fields (name, active/enabled status).

    Args:
        data: Data from the external service
        commit: Whether to commit (default True)

    Returns:
        The updated instance
    """
```

#### Class Methods

##### sync_from_service_data()

```python
@classmethod
def sync_from_service_data(
    cls,
    service_name: str,
    service_data: List[Dict[str, Any]],
    commit=True
):
    """
    Sync multiple records from service data.

    Creates new records or updates existing ones.

    Args:
        service_name: Name of the external service
        service_data: List of data items from the service
        commit: Whether to commit after all updates (default True)

    Returns:
        Dictionary: {"created": n, "updated": m}
    """
```

**Example:**
```python
from app.models.genesys import GenesysGroup

# Fetch groups from Genesys API
groups_data = genesys_service.get_all_groups()

# Sync to database
stats = GenesysGroup.sync_from_service_data("genesys", groups_data)
print(f"Created: {stats['created']}, Updated: {stats['updated']}")
```

---

## Model Mixins

### TimestampMixin

Adds created_at and updated_at timestamp fields.

**Location:** `app/models/base.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `created_at` | DateTime(TZ) | Record creation time (indexed, auto-set) |
| `updated_at` | DateTime(TZ) | Last update time (auto-updated) |

**Usage:**
```python
class MyModel(BaseModel, TimestampMixin):
    __tablename__ = "my_table"
    name = db.Column(db.String(255))

# Timestamps set automatically
item = MyModel(name="Test")
item.save()
print(item.created_at)  # 2025-12-29 12:00:00+00:00
print(item.updated_at)  # 2025-12-29 12:00:00+00:00

# Updated on save
item.name = "Updated"
item.save()
print(item.updated_at)  # 2025-12-29 12:05:00+00:00
```

---

### UserTrackingMixin

Tracks user activity with email, IP, session, and user agent.

**Location:** `app/models/base.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_email` | String(255) | User's email (indexed) |
| `user_agent` | Text | Browser/client info |
| `ip_address` | String(45) | IPv4/IPv6 address (indexed) |
| `session_id` | String(255) | Session identifier (indexed) |

**Usage:**
```python
from flask import g, request

class AccessAttempt(BaseModel, UserTrackingMixin):
    __tablename__ = "access_attempts"
    resource = db.Column(db.String(255))

# In route handler
attempt = AccessAttempt(
    user_email=g.user,
    ip_address=request.remote_addr,
    user_agent=request.headers.get("User-Agent"),
    session_id=session.get("session_id"),
    resource="/admin"
)
attempt.save()
```

---

### ExpirableMixin

Adds expiration functionality with cleanup methods.

**Location:** `app/models/base.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `expires_at` | DateTime(TZ) | Expiration timestamp (indexed) |

#### Instance Methods

##### is_expired()

```python
def is_expired(self) -> bool:
    """
    Check if this record has expired.

    Returns:
        True if expired, False otherwise
    """
```

##### extend_expiration()

```python
def extend_expiration(self, seconds: int, commit=True):
    """
    Extend expiration by specified seconds.

    Args:
        seconds: Number of seconds to extend
        commit: Whether to commit immediately (default True)

    Returns:
        The updated instance
    """
```

#### Class Methods

##### cleanup_expired()

```python
@classmethod
def cleanup_expired(cls, commit=True):
    """
    Remove all expired records for this model.

    Args:
        commit: Whether to commit (default True)

    Returns:
        Number of expired records deleted
    """
```

**Usage:**
```python
from datetime import datetime, timezone, timedelta

class Session(BaseModel, ExpirableMixin):
    __tablename__ = "sessions"
    user_email = db.Column(db.String(255))

# Create with expiration
session = Session(
    user_email="user@example.com",
    expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
)
session.save()

# Check if expired
if session.is_expired():
    print("Session expired")

# Extend expiration
session.extend_expiration(seconds=900)  # +15 minutes

# Cleanup all expired sessions
count = Session.cleanup_expired()
print(f"Removed {count} expired sessions")
```

---

### SerializableMixin

Adds JSON serialization methods.

**Location:** `app/models/base.py`

#### Methods

##### to_dict()

```python
def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Convert model instance to dictionary.

    Args:
        exclude: List of field names to exclude

    Returns:
        Dictionary representation
    """
```

##### to_json_safe()

```python
def to_json_safe(self) -> Dict[str, Any]:
    """
    Convert to JSON-safe dictionary (excludes sensitive fields).

    Automatically excludes fields containing:
    - password, secret, token, key, hash

    Returns:
        Safe dictionary representation
    """
```

**Usage:**
```python
user = User.get_by_id(123)

# Full dict
data = user.to_dict()

# Exclude fields
data = user.to_dict(exclude=["password_hash"])

# Safe serialization (auto-excludes sensitive fields)
safe_data = user.to_json_safe()
```

---

### JSONDataMixin

Adds JSONB field for flexible additional data storage.

**Location:** `app/models/base.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `additional_data` | JSONB | PostgreSQL JSONB field |

#### Methods

##### get_data()

```python
def get_data(self, key: str, default=None):
    """
    Get value from additional_data.

    Args:
        key: Data key
        default: Default if key not found

    Returns:
        Value or default
    """
```

##### set_data()

```python
def set_data(self, key: str, value):
    """
    Set value in additional_data.

    Args:
        key: Data key
        value: Value to store
    """
```

##### update_data()

```python
def update_data(self, data_dict: Dict[str, Any]):
    """
    Update multiple values in additional_data.

    Args:
        data_dict: Dictionary of key-value pairs to update
    """
```

**Usage:**
```python
log = AuditLog(event_type="search", message="Search completed")

# Set individual values
log.set_data("results_count", 5)
log.set_data("services_used", ["ldap", "genesys"])

# Update multiple values
log.update_data({
    "execution_time_ms": 250,
    "cache_hit": False
})

# Get values
count = log.get_data("results_count", 0)
services = log.get_data("services_used", [])
```

---

## Core Models

### User

User account model with role-based access control.

**Location:** `app/models/user.py`

**Extends:** `BaseModel`, `TimestampMixin`

**Table:** `users`

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | Integer | PK | User ID |
| `email` | String(255) | Unique, Not Null, Indexed | User email (Azure AD) |
| `role` | String(50) | Not Null, Default: viewer | Role: admin, editor, viewer |
| `created_at` | DateTime(TZ) | Not Null, Indexed | Creation timestamp |
| `updated_at` | DateTime(TZ) | Not Null | Last update timestamp |

#### Methods

##### validate_role()

```python
@staticmethod
def validate_role(role: str) -> bool:
    """
    Validate role value.

    Args:
        role: Role string

    Returns:
        True if valid role
    """
```

**Valid Roles:**
- `admin` - Full system access
- `editor` - View + edit utilities (blocked numbers)
- `viewer` - Search and view only

**Example:**
```python
from app.models.user import User

# Create user
user = User(email="admin@example.com", role="admin")
user.save()

# Query users
admin_users = User.query.filter_by(role="admin").all()

# Update role
user.update(role="editor")

# Check role
if user.role == "admin":
    # Admin-only operations
    pass
```

---

### Configuration

Encrypted configuration storage.

**Location:** `app/models/configuration.py`

**Extends:** `BaseModel`

**Table:** `configuration`

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | Integer | PK | Config ID |
| `category` | String(50) | Not Null, Indexed | Config category (auth, ldap, etc.) |
| `key` | String(100) | Not Null, Indexed | Config key |
| `value` | BYTEA | Nullable | Encrypted value (or NULL for plaintext) |
| `value_plaintext` | Text | Nullable | Plaintext value (or NULL if encrypted) |
| `is_encrypted` | Boolean | Not Null, Default: False | Encryption flag |

**Unique Constraint:** `(category, key)`

#### Methods

Use `config_get()` and `config_set()` from ConfigurationService instead of direct model access.

**Example:**
```python
from app.services.configuration_service import config_get, config_set

# Get config (auto-decrypts)
secret = config_get("genesys.client_secret")

# Set config (auto-encrypts sensitive keys)
config_set("ldap.bind_password", "new-password")
```

---

### Session

User session management with timeout tracking.

**Location:** `app/models/session.py`

**Extends:** `BaseModel`, `TimestampMixin`, `ExpirableMixin`

**Table:** `sessions`

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | Integer | PK | Session ID |
| `session_id` | String(255) | Unique, Not Null, Indexed | Flask session ID |
| `user_email` | String(255) | Not Null, Indexed | User email |
| `ip_address` | String(45) | Nullable | IP address |
| `user_agent` | Text | Nullable | Browser info |
| `last_activity` | DateTime(TZ) | Not Null | Last activity time |
| `expires_at` | DateTime(TZ) | Not Null, Indexed | Session expiration |
| `created_at` | DateTime(TZ) | Not Null | Creation time |
| `updated_at` | DateTime(TZ) | Not Null | Last update |

**Example:**
```python
from app.models.session import Session
from datetime import datetime, timezone, timedelta

# Create session
session = Session(
    session_id="abc123",
    user_email="user@example.com",
    ip_address="192.168.1.100",
    last_activity=datetime.now(timezone.utc),
    expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
)
session.save()

# Update activity
session.last_activity = datetime.now(timezone.utc)
session.extend_expiration(seconds=900)

# Cleanup expired
count = Session.cleanup_expired()
```

---

## Cache Models

### SearchCache

Search result caching.

**Location:** `app/models/cache.py`

**Extends:** `CacheableModel`

**Table:** `search_cache`

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | Integer | PK | Cache ID |
| `search_query` | String(500) | Not Null, Indexed | Original search query |
| `result_data` | JSONB | Nullable | Cached search results |
| `created_at` | DateTime(TZ) | Not Null | Cache creation time |
| `updated_at` | DateTime(TZ) | Not Null | Last update |
| `expires_at` | DateTime(TZ) | Not Null, Indexed | Cache expiration |

**Example:**
```python
from app.models.cache import SearchCache
from datetime import datetime, timezone, timedelta

# Cache search result
cache = SearchCache(
    search_query="john.doe",
    result_data={"email": "john.doe@example.com", ...},
    expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
)
cache.save()

# Get cached result
cached = SearchCache.get_valid_cache(search_query="john.doe")
if cached:
    result = cached[0].result_data
```

---

### ApiToken

API token storage with expiration.

**Location:** `app/models/api_token.py`

**Extends:** `BaseModel`, `TimestampMixin`, `ExpirableMixin`

**Table:** `api_tokens`

#### Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | Integer | PK | Token ID |
| `service_name` | String(100) | Unique, Not Null | Service name (genesys, microsoft_graph) |
| `access_token` | Text | Not Null | OAuth2 access token |
| `token_type` | String(50) | Default: Bearer | Token type |
| `created_at` | DateTime(TZ) | Not Null | Creation time |
| `updated_at` | DateTime(TZ) | Not Null | Last update |
| `expires_at` | DateTime(TZ) | Not Null, Indexed | Token expiration |

#### Class Methods

##### get_token()

```python
@classmethod
def get_token(cls, service_name: str):
    """
    Get non-expired token for service.

    Args:
        service_name: Service name

    Returns:
        ApiToken instance or None
    """
```

##### upsert_token()

```python
@classmethod
def upsert_token(
    cls,
    service_name: str,
    access_token: str,
    expires_in_seconds: int = 3600,
    token_type: str = "Bearer"
):
    """
    Insert or update API token.

    Args:
        service_name: Service name
        access_token: OAuth2 token
        expires_in_seconds: Token TTL
        token_type: Token type

    Returns:
        ApiToken instance
    """
```

---

### EmployeeProfile

Consolidated employee data from multiple sources.

**Location:** `app/models/employee_profiles.py`

**Extends:** `BaseModel`, `TimestampMixin`

**Table:** `employee_profiles`

**Replaces:** Legacy graph_photos and data_warehouse tables

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `email` | String(255) | Employee email (unique, indexed) |
| `photo_data` | BYTEA | Profile photo (binary) |
| `photo_content_type` | String(50) | Image MIME type |
| `keystone_data` | JSONB | Data from Keystone API |
| `created_at` | DateTime(TZ) | Creation time |
| `updated_at` | DateTime(TZ) | Last update |

**Example:**
```python
from app.models.employee_profiles import EmployeeProfile

# Get profile
profile = EmployeeProfile.query.filter_by(email="user@example.com").first()

if profile:
    # Get photo
    if profile.photo_data:
        photo = base64.b64encode(profile.photo_data).decode()

    # Get Keystone data
    job_code = profile.keystone_data.get("job_code")
```

---

### Genesys Models

Genesys Cloud cached data models.

**Location:** `app/models/genesys.py`

**Extends:** `ServiceDataModel`

#### GenesysGroup

**Table:** `genesys_groups`

#### GenesysSkill

**Table:** `genesys_skills`

#### GenesysLocation

**Table:** `genesys_locations`

**Common Fields** (from ServiceDataModel):
- `service_id` - Genesys ID
- `service_name` - "genesys"
- `raw_data` - Full API response
- `is_active` - Active status
- `created_at`, `updated_at`

**Example:**
```python
from app.models.genesys import GenesysGroup, GenesysSkill

# Get all active groups
groups = GenesysGroup.query.filter_by(is_active=True).all()

# Get specific skill
skill = GenesysSkill.query.filter_by(service_id="skill-123").first()
if skill:
    skill_name = skill.raw_data.get("name")
```

---

## Audit Models

### AuditLog

Comprehensive audit logging.

**Location:** `app/models/audit.py`

**Extends:** `AuditableModel`

**Table:** `audit_log`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `event_type` | String(50) | Event type (indexed) |
| `search_query` | String(500) | Search query (indexed, nullable) |
| `user_email` | String(255) | User email (indexed) |
| `ip_address` | String(45) | IP address (indexed) |
| `user_agent` | Text | Browser/client info |
| `session_id` | String(255) | Session ID (indexed) |
| `success` | Boolean | Success flag (indexed) |
| `message` | Text | Event message |
| `additional_data` | JSONB | Extra data |
| `created_at` | DateTime(TZ) | Timestamp (indexed) |
| `updated_at` | DateTime(TZ) | Last update |

**Event Types:**
- `search` - User searches
- `access` - Access attempts
- `admin` - Admin actions
- `config` - Configuration changes
- `error` - Errors

**Example:**
```python
from app.models.audit import AuditLog

# Log search
log = AuditLog(
    event_type="search",
    user_email="user@example.com",
    search_query="john.doe",
    ip_address="192.168.1.100",
    message="Search completed",
    success=True
)
log.set_data("results_count", 1)
log.set_data("services_used", ["ldap", "genesys"])
log.save()

# Query logs
recent_searches = AuditLog.query.filter_by(
    event_type="search",
    user_email="user@example.com"
).order_by(AuditLog.created_at.desc()).limit(10).all()
```

---

### AccessAttempt

Access attempt tracking (denied and granted).

**Location:** `app/models/access.py`

**Extends:** `AuditableModel`

**Table:** `access_attempts`

#### Fields

Same as AuditableModel plus:

| Field | Type | Description |
|-------|------|-------------|
| `resource` | String(255) | Requested resource (indexed) |
| `required_role` | String(50) | Role required for access |
| `user_role` | String(50) | User's actual role |

---

### ErrorLog

Error and exception logging.

**Location:** `app/models/error.py`

**Extends:** `AuditableModel`

**Table:** `error_log`

#### Fields

Same as AuditableModel plus:

| Field | Type | Description |
|-------|------|-------------|
| `error_type` | String(100) | Error category (indexed) |
| `stack_trace` | Text | Full stack trace |

---

## Job Role Compliance Models

### JobCode

Job codes from HR system (Keystone).

**Location:** `app/models/job_role_compliance.py`

**Extends:** `BaseModel`, `TimestampMixin`

**Table:** `job_codes`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `code` | String(50) | Job code (unique, indexed) |
| `description` | Text | Job description |
| `created_at` | DateTime(TZ) | Creation time |
| `updated_at` | DateTime(TZ) | Last update |

---

### SystemRole

System roles from Genesys Cloud.

**Location:** `app/models/job_role_compliance.py`

**Extends:** `BaseModel`, `TimestampMixin`

**Table:** `system_roles`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `role_name` | String(255) | Role name (unique, indexed) |
| `description` | Text | Role description |
| `created_at` | DateTime(TZ) | Creation time |
| `updated_at` | DateTime(TZ) | Last update |

---

### JobRoleMapping

Maps job codes to required system roles.

**Location:** `app/models/job_role_compliance.py`

**Extends:** `BaseModel`, `TimestampMixin`

**Table:** `job_role_mappings`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `job_code_id` | Integer | FK to job_codes (indexed) |
| `system_role_id` | Integer | FK to system_roles (indexed) |
| `created_at` | DateTime(TZ) | Creation time |
| `updated_at` | DateTime(TZ) | Last update |

**Unique Constraint:** `(job_code_id, system_role_id)`

**Relationships:**
```python
job_code = db.relationship("JobCode", backref="mappings")
system_role = db.relationship("SystemRole", backref="mappings")
```

---

## Utility Functions

### bulk_cleanup_expired()

Clean up expired records from multiple models.

**Location:** `app/models/base.py`

```python
def bulk_cleanup_expired(*model_classes):
    """
    Clean up expired records from multiple model classes.

    Args:
        *model_classes: Model classes with ExpirableMixin

    Returns:
        Dictionary mapping model names to deletion counts
    """
```

**Example:**
```python
from app.models.base import bulk_cleanup_expired
from app.models.cache import SearchCache
from app.models.session import Session
from app.models.api_token import ApiToken

results = bulk_cleanup_expired(SearchCache, Session, ApiToken)
# {"SearchCache": 50, "Session": 10, "ApiToken": 0}
```

---

### get_model_stats()

Get record counts for multiple models.

**Location:** `app/models/base.py`

```python
def get_model_stats(*model_classes):
    """
    Get record counts for multiple models.

    Args:
        *model_classes: Model classes to count

    Returns:
        Dictionary mapping model names to stats
    """
```

**Example:**
```python
from app.models.base import get_model_stats
from app.models.user import User
from app.models.audit import AuditLog

stats = get_model_stats(User, AuditLog)
# {
#     "User": {"total": 25, "active": 25},
#     "AuditLog": {"total": 10000, "active": None}
# }
```

---

### bulk_update_timestamps()

Update timestamps for migration purposes.

**Location:** `app/models/base.py`

```python
def bulk_update_timestamps(*model_classes, commit=True):
    """
    Update timestamps for all records in specified models.

    Args:
        *model_classes: Model classes to update
        commit: Whether to commit (default True)

    Returns:
        Dictionary mapping model names to update counts
    """
```

---

## Database Events

### Automatic Timestamp Updates

Event listener automatically updates timestamps before commit.

**Location:** `app/models/base.py`

```python
@event.listens_for(db.session, "before_commit")
def before_commit(session):
    """Auto-update timestamps before commit."""
    current_time = datetime.now(timezone.utc)

    for obj in session.new:
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = current_time
        if hasattr(obj, "updated_at"):
            obj.updated_at = current_time

    for obj in session.dirty:
        if hasattr(obj, "updated_at"):
            obj.updated_at = current_time
```

**Effect:** You never need to manually set `created_at` or `updated_at` - they're handled automatically.

---

*Last Updated: December 29, 2025*
