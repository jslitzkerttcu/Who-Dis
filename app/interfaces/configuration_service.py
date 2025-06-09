"""Configuration service interface."""

from abc import ABC, abstractmethod
from typing import Any


class IConfigurationService(ABC):
    """Interface for configuration management."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (e.g., 'ldap.host')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if a configuration key exists.

        Args:
            key: Configuration key to check

        Returns:
            True if key exists, False otherwise
        """
        pass
