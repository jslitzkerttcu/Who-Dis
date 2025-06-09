"""Interface for external service data access."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class IExternalServiceRepository(ABC):
    """Interface for external service data access operations."""

    @abstractmethod
    def update_service_data(
        self,
        service_name: str,
        data_type: str,
        service_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update or create external service data."""
        pass

    @abstractmethod
    def get_service_data(
        self, service_name: str, data_type: str, service_id: str
    ) -> Optional[Any]:
        """Get external service data by identifiers."""
        pass

    @abstractmethod
    def query_service_data(self, service_name: str, data_type: str) -> List[Any]:
        """Query external service data by service and type."""
        pass

    @abstractmethod
    def delete_service_data(self, service_name: str, data_type: str) -> None:
        """Delete all service data of a specific type."""
        pass

    @abstractmethod
    def count_service_data(self, service_name: str, data_type: str) -> int:
        """Count service data entries."""
        pass
