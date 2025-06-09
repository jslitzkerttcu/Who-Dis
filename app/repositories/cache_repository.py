"""Cache repository implementation."""

from typing import Optional, Any
from datetime import datetime
from app.interfaces.cache_repository import ICacheRepository
from app.models.unified_cache import CacheEntry


class CacheRepository(ICacheRepository):
    """SQLAlchemy implementation of cache repository."""

    def get_token(self, service_name: str) -> Optional[Any]:
        """Get cached token for a service."""
        return CacheEntry.get_token(service_name)

    def cache_api_token(
        self, service_name: str, access_token: str, expires_in_seconds: int
    ) -> None:
        """Cache an API token."""
        CacheEntry.cache_api_token(service_name, access_token, expires_in_seconds)

    def get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Get cached data by key."""
        return CacheEntry.get_cached_data("general", cache_key)

    def cache_data(
        self, cache_key: str, data: Any, expires_at: Optional[datetime] = None
    ) -> None:
        """Cache data with optional expiration."""
        CacheEntry.cache_data(cache_key, data, expires_at)
