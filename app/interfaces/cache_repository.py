"""Interface for cache data access."""

from abc import ABC, abstractmethod
from typing import Optional, Any
from datetime import datetime


class ICacheRepository(ABC):
    """Interface for cache data access operations."""

    @abstractmethod
    def get_token(self, service_name: str) -> Optional[Any]:
        """Get cached token for a service."""
        pass

    @abstractmethod
    def cache_api_token(
        self, service_name: str, access_token: str, expires_in_seconds: int
    ) -> None:
        """Cache an API token."""
        pass

    @abstractmethod
    def get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Get cached data by key."""
        pass

    @abstractmethod
    def cache_data(
        self, cache_key: str, data: Any, expires_at: Optional[datetime] = None
    ) -> None:
        """Cache data with optional expiration."""
        pass
