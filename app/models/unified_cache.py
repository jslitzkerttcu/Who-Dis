"""
Unified caching model that consolidates all caching functionality.

This replaces separate cache implementations in cache.py, api_token.py,
and graph_photo.py with a single, flexible caching system.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.dialects.postgresql import JSONB
from app.database import db
from app.models.base import CacheableModel


class CacheEntry(CacheableModel):
    """Unified caching model for all cached data."""

    __tablename__ = "cache_entries"

    # Cache identification
    cache_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # 'search', 'api_token', 'photo', 'service_data'
    cache_key = db.Column(db.String(500), nullable=False, index=True)

    # Cache data
    data = db.Column(JSONB, nullable=False)

    # Metadata
    hit_count = db.Column(db.Integer, default=0)
    last_accessed = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Service/source information
    source = db.Column(
        db.String(100), index=True
    )  # 'ldap', 'genesys', 'graph', 'search'

    # Additional metadata
    size_bytes = db.Column(db.Integer)  # For monitoring cache size

    # Unique constraint on cache_type + cache_key
    __table_args__ = (
        db.UniqueConstraint("cache_type", "cache_key", name="uq_cache_type_key"),
    )

    @classmethod
    def get_cached_data(cls, cache_type: str, cache_key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        entry = (
            cls.query.filter_by(cache_type=cache_type, cache_key=cache_key)
            .filter(cls.expires_at > datetime.now(timezone.utc))
            .first()
        )

        if entry:
            # Update access statistics
            entry.hit_count += 1
            entry.last_accessed = datetime.now(timezone.utc)
            db.session.commit()
            return entry.data

        return None

    @classmethod
    def set_cached_data(
        cls,
        cache_type: str,
        cache_key: str,
        data: Any,
        expires_in_seconds: int = 3600,
        source: str = None,
    ) -> "CacheEntry":
        """Set cached data with expiration."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

        # Calculate approximate size
        import json

        try:
            size_bytes = len(json.dumps(data).encode("utf-8"))
        except (TypeError, ValueError):
            size_bytes = None

        # Update existing or create new
        entry = cls.query.filter_by(cache_type=cache_type, cache_key=cache_key).first()
        if entry:
            entry.data = data
            entry.expires_at = expires_at
            entry.updated_at = datetime.now(timezone.utc)
            entry.source = source
            entry.size_bytes = size_bytes
        else:
            entry = cls(
                cache_type=cache_type,
                cache_key=cache_key,
                data=data,
                expires_at=expires_at,
                source=source,
                size_bytes=size_bytes,
            )

        return entry.save()

    @classmethod
    def invalidate_cache(cls, cache_type: str, cache_key: str = None) -> int:
        """Invalidate cache entries."""
        query = cls.query.filter_by(cache_type=cache_type)
        if cache_key:
            query = query.filter_by(cache_key=cache_key)

        count = query.count()
        query.delete()
        db.session.commit()
        return count

    @classmethod
    def get_cache_stats(cls, cache_type: str = None) -> Dict[str, Any]:
        """Get cache statistics."""
        query = cls.query
        if cache_type:
            query = query.filter_by(cache_type=cache_type)

        now = datetime.now(timezone.utc)

        total_entries = query.count()
        valid_entries = query.filter(cls.expires_at > now).count()
        expired_entries = total_entries - valid_entries

        # Get hit statistics
        hit_stats = query.with_entities(
            db.func.sum(cls.hit_count).label("total_hits"),
            db.func.avg(cls.hit_count).label("avg_hits"),
        ).first()

        # Get size statistics
        size_stats = query.with_entities(
            db.func.sum(cls.size_bytes).label("total_size"),
            db.func.avg(cls.size_bytes).label("avg_size"),
        ).first()

        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "total_hits": hit_stats.total_hits or 0,
            "average_hits": float(hit_stats.avg_hits or 0),
            "total_size_bytes": size_stats.total_size or 0,
            "average_size_bytes": float(size_stats.avg_size or 0),
        }

    @classmethod
    def cleanup_expired_by_type(cls, cache_type: str) -> int:
        """Clean up expired entries for specific cache type."""
        count = cls.query.filter(
            cls.cache_type == cache_type, cls.expires_at < datetime.now(timezone.utc)
        ).delete()
        db.session.commit()
        return count

    # API Token caching methods
    @classmethod
    def cache_api_token(
        cls,
        service_name: str,
        access_token: str,
        expires_in_seconds: int,
        additional_data: Dict = None,
    ) -> "CacheEntry":
        """Cache API token for service."""
        data = {
            "access_token": access_token,
            "service_name": service_name,
            "expires_in": expires_in_seconds,
        }
        if additional_data:
            data.update(additional_data)

        return cls.set_cached_data(
            cache_type="api_token",
            cache_key=service_name,
            data=data,
            expires_in_seconds=expires_in_seconds - 60,  # Expire 1 minute early
            source=service_name,
        )

    @classmethod
    def get_api_token(cls, service_name: str) -> Optional[Dict[str, Any]]:
        """Get cached API token for service."""
        return cls.get_cached_data("api_token", service_name)

    @classmethod
    def get_token(cls, service_name: str) -> Optional[Any]:
        """Backward compatibility alias for get_api_token."""
        token_data = cls.get_api_token(service_name)
        if token_data:
            # Create a mock object that has access_token attribute
            class TokenEntry:
                def __init__(self, data):
                    self.access_token = data.get("access_token")
                    self.data = data

            return TokenEntry(token_data)
        return None

    # Photo caching methods
    @classmethod
    def cache_user_photo(
        cls, user_id: str, photo_data: str, hours_to_cache: int = 24
    ) -> "CacheEntry":
        """Cache user photo data."""
        return cls.set_cached_data(
            cache_type="photo",
            cache_key=user_id,
            data={"photo_data": photo_data, "user_id": user_id},
            expires_in_seconds=hours_to_cache * 3600,
            source="graph",
        )

    @classmethod
    def get_user_photo(cls, user_id: str) -> Optional[str]:
        """Get cached user photo."""
        data = cls.get_cached_data("photo", user_id)
        return data.get("photo_data") if data else None

    # Search result caching methods
    @classmethod
    def cache_search_results(
        cls,
        search_query: str,
        results: Dict[str, Any],
        user_email: str = None,
        hours_to_cache: int = 1,
    ) -> "CacheEntry":
        """Cache search results."""
        # Create cache key that includes user context if provided
        cache_key = f"{search_query}:{user_email}" if user_email else search_query

        data = {
            "search_query": search_query,
            "results": results,
            "user_email": user_email,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        return cls.set_cached_data(
            cache_type="search",
            cache_key=cache_key,
            data=data,
            expires_in_seconds=hours_to_cache * 3600,
            source="search",
        )

    @classmethod
    def get_search_results(
        cls, search_query: str, user_email: str = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached search results."""
        cache_key = f"{search_query}:{user_email}" if user_email else search_query
        return cls.get_cached_data("search", cache_key)

    # Service data caching methods
    @classmethod
    def cache_service_data(
        cls,
        service_name: str,
        data_type: str,
        data: List[Dict[str, Any]],
        hours_to_cache: int = 6,
    ) -> "CacheEntry":
        """Cache external service data (groups, skills, locations, etc.)."""
        cache_key = f"{service_name}:{data_type}"

        cache_data = {
            "service_name": service_name,
            "data_type": data_type,
            "data": data,
            "count": len(data),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        return cls.set_cached_data(
            cache_type="service_data",
            cache_key=cache_key,
            data=cache_data,
            expires_in_seconds=hours_to_cache * 3600,
            source=service_name,
        )

    @classmethod
    def get_service_data(
        cls, service_name: str, data_type: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached service data."""
        cache_key = f"{service_name}:{data_type}"
        data = cls.get_cached_data("service_data", cache_key)
        return data.get("data") if data else None

    @classmethod
    def get_cache_overview(cls) -> Dict[str, Any]:
        """Get overview of all cache types."""
        cache_types = db.session.query(cls.cache_type).distinct().all()
        overview = {}

        for (cache_type,) in cache_types:
            overview[cache_type] = cls.get_cache_stats(cache_type)

        # Overall statistics
        overview["overall"] = cls.get_cache_stats()

        return overview

    def extend_expiration(self, seconds: int, commit=True) -> "CacheEntry":
        """Extend cache expiration by specified seconds."""
        return super().extend_expiration(seconds, commit=commit)

    def refresh_data(self, new_data: Any) -> "CacheEntry":
        """Refresh cache data without changing expiration."""
        self.data = new_data
        self.updated_at = datetime.now(timezone.utc)

        # Recalculate size
        import json

        try:
            self.size_bytes = len(json.dumps(new_data).encode("utf-8"))
        except (TypeError, ValueError):
            pass

        return self.save()


# Migration utilities for existing cache models
class CacheMigrationUtils:
    """Utilities for migrating existing cache data to unified model."""

    @staticmethod
    def migrate_api_tokens():
        """Migrate existing API tokens to unified cache."""
        try:
            from app.models.api_token import ApiToken

            migrated_count = 0
            for token in ApiToken.query.all():
                CacheEntry.cache_api_token(
                    service_name=token.service_name,
                    access_token=token.access_token,
                    expires_in_seconds=int(
                        (token.expires_at - datetime.now(timezone.utc)).total_seconds()
                    ),
                    additional_data=token.additional_data,
                )
                migrated_count += 1

            return migrated_count
        except ImportError:
            return 0

    @staticmethod
    def migrate_graph_photos():
        """Migrate existing graph photos to unified cache."""
        try:
            from app.models.graph_photo import GraphPhoto

            migrated_count = 0
            for photo in GraphPhoto.query.all():
                CacheEntry.cache_user_photo(
                    user_id=photo.user_id,
                    photo_data=photo.photo_data,
                    hours_to_cache=24,
                )
                migrated_count += 1

            return migrated_count
        except ImportError:
            return 0

    @staticmethod
    def migrate_search_cache():
        """Migrate existing search cache to unified cache."""
        try:
            from app.models.cache import SearchCache

            migrated_count = 0
            for cache in SearchCache.query.all():
                CacheEntry.cache_search_results(
                    search_query=cache.search_query,
                    results=cache.result_data,
                    user_email=cache.user_email,
                    hours_to_cache=1,
                )
                migrated_count += 1

            return migrated_count
        except ImportError:
            return 0


# Backward compatibility aliases
SearchCache = CacheEntry
ApiToken = CacheEntry
GraphPhoto = CacheEntry
