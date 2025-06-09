"""Interface for log data access."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime


class ILogRepository(ABC):
    """Interface for log data access operations."""

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
    def log_access(
        self,
        user_email: str,
        action: str,
        target_resource: str,
        success: bool = True,
        **kwargs,
    ) -> None:
        """Log an access event."""
        pass

    @abstractmethod
    def log_admin_action(
        self,
        user_email: str,
        action: str,
        target_resource: str,
        additional_data: Optional[Dict[str, Any]] = None,
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

    @abstractmethod
    def query_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[str] = None,
        user_email: Optional[str] = None,
        search_query: Optional[str] = None,
        ip_address: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Any]:
        """Query log entries with filters."""
        pass

    @abstractmethod
    def count_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[str] = None,
        user_email: Optional[str] = None,
        search_query: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> int:
        """Count log entries with filters."""
        pass
