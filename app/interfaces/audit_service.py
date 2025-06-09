"""Audit service interfaces - separated for CQRS pattern."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime


class IAuditLogger(ABC):
    """Interface for audit logging (write operations)."""

    @abstractmethod
    def log_search(
        self,
        user_email: str,
        search_query: str,
        results_count: int,
        services: List[str],
        **kwargs,
    ) -> None:
        """Log a search event."""
        pass

    @abstractmethod
    def log_access_denial(
        self, user_email: str, requested_resource: str, reason: str, **kwargs
    ) -> None:
        """Log an access denial event."""
        pass

    @abstractmethod
    def log_admin_action(
        self,
        user_email: str,
        action: str,
        target: str,
        details: Dict[str, Any],
        **kwargs,
    ) -> None:
        """Log an administrative action."""
        pass

    @abstractmethod
    def log_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Log an error event."""
        pass


class IAuditQueryService(ABC):
    """Interface for audit querying (read operations)."""

    @abstractmethod
    def get_recent_logs(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
        user_email: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent audit logs with optional filters."""
        pass

    @abstractmethod
    def get_search_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get search statistics for the specified period."""
        pass

    @abstractmethod
    def get_user_activity(
        self, user_email: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get activity logs for a specific user."""
        pass
