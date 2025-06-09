"""Token service interface for OAuth2 authentication."""

from abc import ABC, abstractmethod
from typing import Optional


class ITokenService(ABC):
    """Interface for services that manage OAuth2 tokens."""

    @abstractmethod
    def get_access_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Access token string or None if unable to obtain
        """
        pass

    @abstractmethod
    def refresh_token_if_needed(self) -> bool:
        """
        Check token validity and refresh if needed.

        Returns:
            True if token is valid (existing or newly fetched), False otherwise
        """
        pass

    @property
    @abstractmethod
    def token_service_name(self) -> str:
        """Get the name used for token storage/identification."""
        pass
