"""
Base service classes implementing common patterns across all services.

This module provides base classes that extract common functionality from
all services to reduce code duplication and ensure consistent patterns.
"""

import logging
from abc import abstractmethod
from typing import Dict, Any, Optional, List
import requests
from requests.exceptions import Timeout, ConnectionError, RequestException
from app.services.configuration_service import config_get

logger = logging.getLogger(__name__)


class BaseConfigurableService:
    """Base class for services that need configuration management."""

    def __init__(self, config_prefix: str):
        """
        Initialize service with configuration prefix.

        Args:
            config_prefix: The prefix for configuration keys (e.g., 'ldap', 'genesys', 'graph')
        """
        self._config_prefix = config_prefix
        self._config_loaded = False
        self._config_cache: Dict[str, Any] = {}

    def _load_config(self):
        """Load configuration lazily when first needed. Override in subclasses for custom loading."""
        if not self._config_loaded:
            # Default implementation - subclasses can override
            self._config_loaded = True

    def _get_config(self, key: str, default=None, config_type=str):
        """
        Get configuration value with caching and type conversion.

        Args:
            key: Configuration key (without prefix)
            default: Default value if key not found
            config_type: Type to convert value to (str, int, bool)

        Returns:
            Configuration value converted to specified type
        """
        full_key = f"{self._config_prefix}.{key}"

        if full_key not in self._config_cache:
            value = config_get(full_key, default)

            # Type conversion
            if config_type is bool and isinstance(value, str):
                value = value.lower() == "true"
            elif config_type is int and value is not None:
                value = int(value)

            self._config_cache[full_key] = value

        return self._config_cache[full_key]

    def _clear_config_cache(self):
        """Clear configuration cache to force reload."""
        self._config_cache.clear()
        self._config_loaded = False


class BaseAPIService(BaseConfigurableService):
    """Base class for services that interact with REST APIs."""

    def __init__(self, config_prefix: str):
        super().__init__(config_prefix)
        self._default_timeout = 15

    @property
    def timeout(self) -> int:
        """Get API timeout from configuration."""
        return int(self._get_config("api_timeout", self._default_timeout, int))

    def _get_headers(
        self, token: Optional[str] = None, **additional_headers
    ) -> Dict[str, str]:
        """
        Get standard HTTP headers.

        Args:
            token: Optional Bearer token
            **additional_headers: Additional headers to include

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"WhoDis-Service/{self._config_prefix}",
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        headers.update(additional_headers)
        return headers

    def _make_request(
        self,
        method: str,
        url: str,
        token: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Make HTTP request with standard error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            token: Optional Bearer token
            timeout: Request timeout (defaults to service timeout)
            **kwargs: Additional arguments for requests

        Returns:
            Response object

        Raises:
            TimeoutError: If request times out
            ConnectionError: If connection fails
            RequestException: For other HTTP errors
        """
        timeout = timeout or self.timeout
        headers = kwargs.pop("headers", {})
        headers.update(self._get_headers(token, **headers))

        try:
            logger.debug(f"Making {method} request to {url} with timeout {timeout}s")
            response = requests.request(
                method=method, url=url, headers=headers, timeout=timeout, **kwargs
            )

            # Log response status
            logger.debug(f"Response: {response.status_code} from {url}")

            return response

        except Timeout:
            error_msg = (
                f"{self._config_prefix.title()} API timeout after {timeout} seconds"
            )
            logger.error(f"{error_msg}: {url}")
            raise TimeoutError(f"{error_msg}. Please try a more specific search term.")

        except ConnectionError as e:
            error_msg = f"Connection error to {self._config_prefix.title()} API"
            logger.error(f"{error_msg}: {url} - {str(e)}")
            raise ConnectionError(f"{error_msg}: {str(e)}")

        except RequestException as e:
            error_msg = f"Error making request to {self._config_prefix.title()} API"
            logger.error(f"{error_msg}: {url} - {str(e)}")
            raise RequestException(f"{error_msg}: {str(e)}")

    def _handle_response(
        self, response: requests.Response, expect_json: bool = True
    ) -> Any:
        """
        Handle API response with standard error checking.

        Args:
            response: Response object
            expect_json: Whether to parse response as JSON

        Returns:
            Response data (JSON parsed if expect_json=True)

        Raises:
            RequestException: If response indicates an error
        """
        if response.status_code >= 400:
            error_msg = (
                f"{self._config_prefix.title()} API error: {response.status_code}"
            )
            logger.error(f"{error_msg} - {response.text}")
            raise RequestException(f"{error_msg}")

        if expect_json:
            try:
                return response.json()
            except ValueError as e:
                logger.error(
                    f"Failed to parse JSON response from {self._config_prefix.title()} API: {str(e)}"
                )
                raise RequestException(
                    f"Invalid JSON response from {self._config_prefix.title()} API"
                )

        return response.content

    @abstractmethod
    def test_connection(self) -> bool:
        """Test service connection. Must be implemented by subclasses."""
        pass


class BaseTokenService(BaseAPIService):
    """Base class for services with OAuth2 token management."""

    def __init__(self, config_prefix: str, token_service_name: str):
        super().__init__(config_prefix)
        self._token_service_name = token_service_name

    def _get_cached_token(self) -> Optional[str]:
        """Get token from database cache."""
        try:
            from flask import current_app

            if current_app:
                # Try both cache models for compatibility
                try:
                    from app.models.unified_cache import CacheEntry

                    token_data = CacheEntry.get_token(self._token_service_name)
                    if token_data and hasattr(token_data, "access_token"):
                        logger.debug(
                            f"Using cached token for {self._token_service_name} from CacheEntry"
                        )
                        return str(token_data.access_token)
                except ImportError:
                    pass

                try:
                    from app.models.api_token import ApiToken

                    token_data = ApiToken.get_token(self._token_service_name)
                    if token_data and hasattr(token_data, "access_token"):
                        logger.debug(
                            f"Using cached token for {self._token_service_name} from ApiToken"
                        )
                        return str(token_data.access_token)
                except ImportError:
                    pass

        except RuntimeError:
            logger.debug(
                f"No Flask app context for {self._token_service_name} token lookup"
            )
        except Exception as e:
            logger.error(
                f"Error getting {self._token_service_name} token from database: {e}"
            )

        return None

    def _store_token(self, access_token: str, expires_in: int = 3600):
        """Store token in database cache."""
        try:
            from flask import current_app

            if current_app:
                # Try both cache models for compatibility
                try:
                    from app.models.unified_cache import CacheEntry

                    CacheEntry.cache_api_token(
                        service_name=self._token_service_name,
                        access_token=access_token,
                        expires_in_seconds=expires_in,
                    )
                    logger.debug(
                        f"Stored {self._token_service_name} token in CacheEntry"
                    )
                    return
                except ImportError:
                    pass

                try:
                    from app.models.api_token import ApiToken

                    ApiToken.cache_api_token(
                        service_name=self._token_service_name,
                        access_token=access_token,
                        expires_in_seconds=expires_in,
                    )
                    logger.debug(f"Stored {self._token_service_name} token in ApiToken")
                    return
                except ImportError:
                    pass

        except RuntimeError:
            pass
        except Exception as e:
            logger.error(f"Error storing {self._token_service_name} token: {e}")

    def get_access_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if necessary."""
        # Check cache first
        token = self._get_cached_token()
        if token:
            return token

        # Fetch new token
        logger.debug(f"Fetching new token for {self._token_service_name}")
        return self._fetch_new_token()

    @abstractmethod
    def _fetch_new_token(self) -> Optional[str]:
        """Fetch new token from service. Must be implemented by subclasses."""
        pass

    def refresh_token_if_needed(self) -> bool:
        """Check and refresh token if needed. Returns True if token is valid."""
        try:
            token = self.get_access_token()
            return token is not None
        except Exception as e:
            logger.error(f"Error refreshing {self._token_service_name} token: {str(e)}")
            return False


class BaseSearchService(BaseConfigurableService):
    """Base class for services with search functionality."""

    def _normalize_search_term(self, search_term: str) -> List[str]:
        """
        Normalize search term and generate variations.

        Args:
            search_term: Original search term

        Returns:
            List of search term variations
        """
        variations = [search_term.strip()]

        # Handle email addresses - extract username part
        if "@" in search_term:
            username = search_term.split("@")[0].strip()
            if username not in variations:
                variations.append(username)

        # Remove empty variations
        return [v for v in variations if v]

    def _format_multiple_results(
        self, results: List[Dict[str, Any]], total: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Format multiple search results in standard format.

        Args:
            results: List of result dictionaries
            total: Total number of results (defaults to len(results))

        Returns:
            Standardized multiple results dictionary
        """
        return {
            "multiple_results": True,
            "results": results,
            "total": total or len(results),
        }

    def _should_return_multiple_results(
        self, results: List[Any], search_term: str
    ) -> bool:
        """
        Determine if multiple results should be returned based on search context.

        Args:
            results: List of found results
            search_term: Original search term

        Returns:
            True if multiple results should be returned
        """
        # If we have multiple results and the search term is ambiguous (short or common)
        if len(results) > 1:
            # For very specific searches (email addresses), prefer exact matches
            if "@" in search_term:
                return len(results) > 3  # Only return multiple if many matches
            # For short searches, always return multiple
            elif len(search_term.strip()) < 4:
                return True
            # For longer searches, return multiple if we have many matches
            else:
                return len(results) > 2

        return False

    @abstractmethod
    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        """Search for a user. Must be implemented by subclasses."""
        pass


class BaseCacheService(BaseConfigurableService):
    """Base class for services with database caching functionality."""

    def __init__(self, config_prefix: str):
        super().__init__(config_prefix)
        self._default_cache_timeout = 1800  # 30 minutes
        self._default_refresh_period = 21600  # 6 hours

    @property
    def cache_timeout(self) -> int:
        """Get cache timeout in seconds."""
        return int(self._get_config("cache_timeout", self._default_cache_timeout, int))

    @property
    def cache_refresh_period(self) -> int:
        """Get cache refresh period in seconds."""
        return int(
            self._get_config("cache_refresh_period", self._default_refresh_period, int)
        )

    def needs_refresh(self) -> bool:
        """
        Check if cache needs refresh based on last update time.
        Default implementation always returns True - override in subclasses.
        """
        return True

    @abstractmethod
    def refresh_cache(self) -> Dict[str, int]:
        """
        Refresh cache from external service.

        Returns:
            Dictionary with statistics about the refresh operation
        """
        pass

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        Default implementation returns empty dict - override in subclasses.
        """
        return {}


# Composite base class for API services that need both token management and search
class BaseAPITokenService(BaseTokenService, BaseSearchService):
    """Composite base class for API services with token management and search."""

    def __init__(self, config_prefix: str, token_service_name: str):
        BaseTokenService.__init__(self, config_prefix, token_service_name)
        BaseSearchService.__init__(self, config_prefix)
