"""Cache repository implementation."""

from typing import Optional, Any
from datetime import datetime
from app.interfaces.cache_repository import ICacheRepository
from app.models.api_token import ApiToken
from app.models.cache import SearchCache


class CacheRepository(ICacheRepository):
    """SQLAlchemy implementation of cache repository."""

    def get_token(self, service_name: str) -> Optional[Any]:
        """Get cached token for a service."""
        token = ApiToken.get_token(service_name)
        return token.access_token if token else None

    def cache_api_token(
        self, service_name: str, access_token: str, expires_in_seconds: int
    ) -> None:
        """Cache an API token."""
        ApiToken.upsert_token(service_name, access_token, expires_in_seconds)

    def get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Get cached data by key."""
        # For general caching, use SearchCache with a "general" search_type
        cache = SearchCache.query.filter_by(
            search_query=cache_key, search_type="general"
        ).first()
        return cache.result_data if cache and not cache.is_expired else None

    def cache_data(
        self, cache_key: str, data: Any, expires_at: Optional[datetime] = None
    ) -> None:
        """Cache data with optional expiration."""
        from datetime import timedelta

        # Default expiration if not provided
        if expires_at is None:
            expires_at = datetime.now() + timedelta(hours=1)

        # Use SearchCache for general data caching
        cache = SearchCache.query.filter_by(
            search_query=cache_key, search_type="general"
        ).first()

        if cache:
            cache.update(result_data=data, expires_at=expires_at)
        else:
            cache = SearchCache(
                search_query=cache_key,
                search_type="general",
                result_data=data,
                expires_at=expires_at,
            )
            cache.save()
