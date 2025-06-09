# Models package with unified consolidated models
from .unified_log import LogEntry
from .unified_cache import CacheEntry
from .external_service import ExternalServiceData
from .session import UserSession
from .user import User
from .user_note import UserNote

# Backward compatibility aliases
AuditLog = LogEntry
ErrorLog = LogEntry
AccessAttempt = LogEntry

# Cache model aliases
SearchCache = CacheEntry
ApiToken = CacheEntry
GraphPhoto = CacheEntry

# External service aliases
GenesysGroup = ExternalServiceData
GenesysLocation = ExternalServiceData
GenesysSkill = ExternalServiceData

__all__ = [
    # New unified models
    "LogEntry",
    "CacheEntry",
    "ExternalServiceData",
    "UserSession",
    "User",
    "UserNote",
    # Backward compatibility aliases
    "AuditLog",
    "ErrorLog",
    "AccessAttempt",
    "SearchCache",
    "ApiToken",
    "GraphPhoto",
    "GenesysGroup",
    "GenesysLocation",
    "GenesysSkill",
]
