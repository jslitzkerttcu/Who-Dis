"""External service repository implementation."""

from typing import Optional, Dict, Any, List
from app.interfaces.external_service_repository import IExternalServiceRepository
from app.models.external_service import ExternalServiceData


class ExternalServiceRepository(IExternalServiceRepository):
    """SQLAlchemy implementation of external service repository."""

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
        ExternalServiceData.update_service_data(
            service_name, data_type, service_id, name or "", raw_data or {}, description
        )

    def get_service_data(
        self, service_name: str, data_type: str, service_id: str
    ) -> Optional[Any]:
        """Get external service data by identifiers."""
        return ExternalServiceData.query.filter_by(
            service_name=service_name, data_type=data_type, service_id=service_id
        ).first()

    def query_service_data(self, service_name: str, data_type: str) -> List[Any]:
        """Query external service data by service and type."""
        result = ExternalServiceData.query.filter_by(
            service_name=service_name, data_type=data_type
        ).all()
        return result if result is not None else []

    def delete_service_data(self, service_name: str, data_type: str) -> None:
        """Delete all service data of a specific type."""
        ExternalServiceData.query.filter_by(
            service_name=service_name, data_type=data_type
        ).delete()

    def count_service_data(self, service_name: str, data_type: str) -> int:
        """Count service data entries."""
        result = ExternalServiceData.query.filter_by(
            service_name=service_name, data_type=data_type
        ).count()
        return result if result is not None else 0
