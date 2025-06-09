"""Log repository implementation."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from app.interfaces.log_repository import ILogRepository
from app.models.unified_log import LogEntry


class LogRepository(ILogRepository):
    """SQLAlchemy implementation of log repository."""

    def log_search(
        self,
        user_email: str,
        search_query: str,
        results_count: int,
        services: List[str],
        **kwargs,
    ) -> None:
        """Log a search event."""
        LogEntry.log_search(user_email, search_query, results_count, services, **kwargs)

    def log_access(
        self,
        user_email: str,
        action: str,
        target_resource: str,
        success: bool = True,
        **kwargs,
    ) -> None:
        """Log an access event."""
        LogEntry.log_access(user_email, action, target_resource, success=success, **kwargs)

    def log_admin_action(
        self,
        user_email: str,
        action: str,
        target_resource: str,
        additional_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log an administrative action."""
        LogEntry.log_admin_action(user_email, action, target_resource, **kwargs)

    def log_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Log an error event."""
        LogEntry.log_error(error_type, error_message, stack_trace or "", **kwargs)

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
        result = LogEntry.query_logs(
            start_date,
            end_date,
            event_type,
            user_email,
            search_query,
            ip_address,
            limit,
            offset,
        )
        return result if result is not None else []

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
        result = LogEntry.count_logs(
            start_date, end_date, event_type, user_email, search_query, ip_address
        )
        return result if result is not None else 0
