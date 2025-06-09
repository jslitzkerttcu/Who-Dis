"""
Base service classes for WhoDis application.

This module provides base classes that implement common patterns used across
multiple services, reducing code duplication and ensuring consistency.
"""

import logging
from abc import abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import requests
from requests.exceptions import Timeout, ConnectionError

from app.services.configuration_service import config_get
from app.utils.error_handler import handle_service_errors
from app.interfaces.cache_repository import ICacheRepository

logger = logging.getLogger(__name__)


class BaseConfigurableService:
    """Base class for services that use configuration."""

    def __init__(self, config_prefix: str):
        """
        Initialize with a configuration prefix.

        Args:
            config_prefix: Prefix for configuration keys (e.g., 'genesys', 'graph')
        """
        self._config_prefix = config_prefix
        self._config_cache: Dict[str, Any] = {}

    def _get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with caching.

        Args:
            key: Configuration key (without prefix)
            default: Default value if not found

        Returns:
            Configuration value
        """
        full_key = f"{self._config_prefix}.{key}"

        if full_key not in self._config_cache:
            self._config_cache[full_key] = config_get(full_key, default)

        return self._config_cache[full_key]

    def _clear_config_cache(self):
        """Clear the configuration cache to force reload."""
        self._config_cache.clear()

    def _load_config(self):
        """Load configuration - can be overridden by subclasses."""
        # Base implementation does nothing - subclasses can override
        pass


class BaseAPIService(BaseConfigurableService):
    """Base class for API-based services with common HTTP functionality."""

    def __init__(self, config_prefix: str):
        """
        Initialize API service.

        Args:
            config_prefix: Prefix for configuration keys
        """
        super().__init__(config_prefix)
        self._base_url = None

    @property
    def timeout(self) -> int:
        """Get API timeout in seconds."""
        return int(self._get_config("api_timeout", "15"))

    @property
    def base_url(self) -> str:
        """Get base URL for API - can be overridden in subclasses."""
        if self._base_url is None:
            self._base_url = self._get_config("base_url", "")
        return self._base_url or ""

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """
        Get standard headers for API requests.

        Args:
            token: Optional bearer token

        Returns:
            Headers dictionary
        """
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    @handle_service_errors(raise_errors=True)
    def _make_request(
        self, method: str, url: str, token: Optional[str] = None, **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with standard error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            token: Optional bearer token
            **kwargs: Additional arguments for requests

        Returns:
            Response object

        Raises:
            TimeoutError: If request times out
            ConnectionError: If connection fails
            requests.HTTPError: If response status is not successful
        """
        # Set defaults
        kwargs.setdefault("timeout", self.timeout)

        # Add headers if not provided
        if "headers" not in kwargs:
            kwargs["headers"] = self._get_headers(token)
        elif token and "Authorization" not in kwargs["headers"]:
            kwargs["headers"]["Authorization"] = f"Bearer {token}"

        try:
            logger.debug(f"{method} {url}")
            response = requests.request(method, url, **kwargs)

            # Log response status
            logger.debug(f"Response: {response.status_code}")

            # Raise for HTTP errors
            response.raise_for_status()

            return response

        except Timeout:
            logger.error(f"Timeout after {self.timeout} seconds: {url}")
            raise TimeoutError(
                f"{self._config_prefix.title()} request timed out after {self.timeout} seconds. "
                f"Please try again."
            )
        except ConnectionError as e:
            logger.error(f"Connection error to {url}: {str(e)}")
            raise ConnectionError(
                f"Failed to connect to {self._config_prefix.title()} API"
            )
        except requests.HTTPError as e:
            logger.error(
                f"HTTP error from {url}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error making request to {url}: {str(e)}")
            raise

    def _handle_response(self, response: requests.Response) -> Any:
        """
        Handle API response and extract JSON data.

        Args:
            response: HTTP response object

        Returns:
            Parsed JSON data or None
        """
        try:
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(
                    f"API returned status {response.status_code}: {response.text}"
                )
                return None
        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            return None

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test service connection.

        Returns:
            True if connection successful, False otherwise
        """
        pass


class BaseTokenService(BaseAPIService):
    """Base class for services with OAuth2 token management."""

    def __init__(
        self,
        config_prefix: str,
        token_service_name: str,
        cache_repository: Optional[ICacheRepository] = None,
    ):
        """
        Initialize token service.

        Args:
            config_prefix: Prefix for configuration keys
            token_service_name: Name for token storage (e.g., 'genesys', 'microsoft_graph')
            cache_repository: Repository for token caching (optional, uses default if None)
        """
        super().__init__(config_prefix)
        self._token_service_name = token_service_name
        self._cache_repository = cache_repository

    def _get_cached_token(self) -> Optional[str]:
        """
        Get token from cache repository.

        Returns:
            Cached token if available and valid, None otherwise
        """
        try:
            if self._cache_repository:
                token_data = self._cache_repository.get_token(self._token_service_name)
            else:
                # Fallback to direct model access for backward compatibility
                from flask import current_app

                if current_app:
                    from app.models.unified_cache import CacheEntry

                    token_data = CacheEntry.get_token(self._token_service_name)
                else:
                    return None

            if token_data and hasattr(token_data, "access_token"):
                logger.debug(
                    f"Using cached {self._token_service_name} token from database"
                )
                return str(token_data.access_token)
        except RuntimeError:
            logger.debug(
                f"No Flask app context for {self._token_service_name} token lookup"
            )
        except Exception as e:
            logger.error(
                f"Error getting {self._token_service_name} token from database: {e}"
            )

        return None

    def _store_token(self, access_token: str, expires_in: int = 3600) -> None:
        """
        Store token in cache repository.

        Args:
            access_token: The access token to store
            expires_in: Token expiration time in seconds
        """
        try:
            if self._cache_repository:
                self._cache_repository.cache_api_token(
                    service_name=self._token_service_name,
                    access_token=access_token,
                    expires_in_seconds=expires_in,
                )
            else:
                # Fallback to direct model access for backward compatibility
                from flask import current_app

                if current_app:
                    from app.models.unified_cache import CacheEntry

                    CacheEntry.cache_api_token(
                        service_name=self._token_service_name,
                        access_token=access_token,
                        expires_in_seconds=expires_in,
                    )
            logger.debug(f"Stored {self._token_service_name} token in database")
        except RuntimeError:
            logger.debug("No Flask app context for token storage")
        except Exception as e:
            logger.error(f"Error storing {self._token_service_name} token: {e}")

    def _get_access_token(self) -> Optional[str]:
        """
        Get access token, using cache if available.

        Returns:
            Access token or None if unable to obtain
        """
        # Try cached token first
        token = self._get_cached_token()
        if token:
            return token

        # Fetch new token
        logger.debug(f"Fetching new {self._token_service_name} token")
        return self._fetch_new_token()

    @abstractmethod
    def _fetch_new_token(self) -> Optional[str]:
        """
        Fetch a new access token from the service.

        Must be implemented by subclasses to handle service-specific auth.
        Should call _store_token() to cache the token.

        Returns:
            Access token or None if unable to obtain
        """
        pass

    def get_access_token(self) -> Optional[str]:
        """
        Public method to get access token.

        Returns:
            Access token or None if unable to obtain
        """
        return self._get_access_token()

    def refresh_token_if_needed(self) -> bool:
        """
        Check and refresh token if needed.

        Returns:
            True if token is valid (either existing or newly fetched)
        """
        try:
            token = self._get_access_token()
            return token is not None
        except Exception as e:
            logger.error(f"Error refreshing {self._token_service_name} token: {str(e)}")
            return False


class BaseSearchService(BaseConfigurableService):
    """Base class for services with user search functionality."""

    def __init__(self, config_prefix: str):
        """Initialize search service with configuration prefix."""
        super().__init__(config_prefix)

    def _normalize_search_term(self, search_term: str) -> List[str]:
        """
        Normalize search term and generate variations.

        Args:
            search_term: The search term to normalize

        Returns:
            List of search term variations
        """
        variations = [search_term]

        # Handle email addresses
        if "@" in search_term:
            username = search_term.split("@")[0]
            variations.append(username)

        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for v in variations:
            if v not in seen:
                seen.add(v)
                unique_variations.append(v)

        return unique_variations

    def _format_multiple_results(
        self, results: List[Dict[str, Any]], total: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Format multiple search results in standard format.

        Args:
            results: List of result dictionaries
            total: Total number of results (if different from len(results))

        Returns:
            Formatted results dictionary
        """
        return {
            "multiple_results": True,
            "results": results,
            "total": total or len(results),
        }

    @abstractmethod
    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        """
        Search for a user.

        Args:
            search_term: Term to search for (email, username, etc.)

        Returns:
            User data dictionary or None if not found
            If multiple results, returns dict with 'multiple_results' = True
        """
        pass


class BaseCacheService(BaseConfigurableService):
    """Base class for services with database caching functionality."""

    def __init__(self, config_prefix: str):
        """
        Initialize cache service.

        Args:
            config_prefix: Prefix for configuration keys
        """
        super().__init__(config_prefix)

    @property
    def cache_timeout(self) -> int:
        """Get cache timeout in seconds."""
        return int(self._get_config("cache_timeout", "30"))

    @property
    def cache_refresh_period(self) -> int:
        """Get cache refresh period in seconds."""
        return int(self._get_config("cache_refresh_period", "21600"))  # 6 hours

    def needs_refresh(self, last_update: datetime) -> bool:
        """
        Check if cache needs refresh based on last update time.

        Args:
            last_update: Last update timestamp

        Returns:
            True if cache needs refresh
        """
        # Ensure timezone consistency
        now = datetime.now(timezone.utc)
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)

        time_since_update = now - last_update
        return time_since_update > timedelta(seconds=self.cache_refresh_period)

    @abstractmethod
    def refresh_cache(self) -> Dict[str, int]:
        """
        Refresh cache data.

        Returns:
            Dictionary with refresh statistics (e.g., {'items': 100})
        """
        pass


# Composite base classes for common combinations


class BaseAPITokenService(BaseTokenService, BaseSearchService):
    """Base class for API services with token management and search."""

    def __init__(
        self,
        config_prefix: str,
        token_service_name: str,
        cache_repository: Optional[ICacheRepository] = None,
    ):
        """
        Initialize API token service.

        Args:
            config_prefix: Prefix for configuration keys
            token_service_name: Name for token storage
            cache_repository: Repository for token caching (optional, uses default if None)
        """
        BaseTokenService.__init__(
            self, config_prefix, token_service_name, cache_repository
        )

    # Inherits all functionality from both base classes
