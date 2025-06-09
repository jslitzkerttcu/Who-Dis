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

# Create singleton instance - SimpleConfig now implements IConfigurationService directly
configuration_service: IConfigurationService = SimpleConfig()

__all__ = [
    "configuration_service",
    "config_get",
    "config_set",
    "config_delete",
    "config_get_all",
    "config_clear_cache",
    "config_exists",
]
