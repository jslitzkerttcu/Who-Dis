"""Search service interface for user lookups."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class ISearchService(ABC):
    """Interface for services that search for user information."""

    @abstractmethod
    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        """
        Search for a user by email, username, or other identifier.

        Args:
            search_term: The term to search for

        Returns:
            User data dictionary or None if not found.
            If multiple results found, returns dict with:
                - multiple_results: True
                - results: List of user dictionaries
                - total: Total number of results
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the service is available and properly configured.

        Returns:
            True if service is operational, False otherwise
        """
        pass

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Get the name of this search service."""
        pass
