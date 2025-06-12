"""
Configuration service implementing IConfigurationService interface.

This module now provides a direct instance of SimpleConfig which implements
the IConfigurationService interface, eliminating the duplication that existed
with the wrapper approach.
"""

from app.interfaces.configuration_service import IConfigurationService
from app.services.simple_config import (
    SimpleConfig,
    config_get,
    config_set,
    config_delete,
    config_get_all,
    config_clear_cache,
    config_exists,
)

# Lazy initialization of configuration service
_configuration_service = None


def get_configuration_service() -> IConfigurationService:
    """Get the singleton configuration service instance."""
    global _configuration_service
    if _configuration_service is None:
        _configuration_service = SimpleConfig()
    return _configuration_service


# For backward compatibility, create a wrapper class
class LazyConfigurationService:
    """Lazy wrapper for configuration service."""

    def __getattr__(self, name):
        return getattr(get_configuration_service(), name)


# Export the lazy wrapper
configuration_service = LazyConfigurationService()

__all__ = [
    "get_configuration_service",
    "configuration_service",
    "config_get",
    "config_set",
    "config_delete",
    "config_get_all",
    "config_clear_cache",
    "config_exists",
]
