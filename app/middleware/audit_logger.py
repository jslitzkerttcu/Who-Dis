from flask import request
from typing import Optional


class AuditLogger:
    """Handles audit logging for authentication events"""

    def log_access_denied(
        self, user_email: Optional[str] = None, user_role: Optional[str] = None
    ) -> None:
        """
        Log denied access attempts to audit database

        Args:
            user_email: User's email (if authenticated)
            user_role: User's role (if determined)
        """
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        request_path = request.path

        email_display = user_email if user_email else "unauthenticated"
        role_display = user_role if user_role else "unknown"

        # Log to audit database
        try:
            from app.services.audit_service_postgres import audit_service
            from app.models.unified_log import LogEntry

            # Log access attempt using unified logging
            LogEntry.log_access_denied(
                user_email=email_display
                if email_display and email_display != "unauthenticated"
                else "",
                target_resource=request_path,
                reason="Insufficient permissions"
                if user_email
                else "Not authenticated",
                ip_address=client_ip,
                user_agent=request.headers.get("User-Agent"),
                request_path=request_path,
                request_method=request.method,
            )

            # Also log to audit log
            audit_service.log_access(
                user_email=email_display,
                action="access_denied",
                target_resource=request_path,
                user_role=role_display,
                ip_address=client_ip,
                user_agent=request.headers.get("User-Agent"),
                success=False,
                error_message="Insufficient permissions",
            )
        except Exception:
            # Don't let audit logging failures break authentication
            pass

    def log_authentication_success(self, user_email: str, user_role: str) -> None:
        """Log successful authentication"""
        try:
            from app.services.audit_service_postgres import audit_service

            audit_service.log_access(
                user_email=user_email,
                action="authentication",
                target_resource=request.path,
                user_role=user_role,
                ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
                user_agent=request.headers.get("User-Agent"),
                success=True,
            )
        except Exception:
            # Don't let audit logging failures break authentication
            pass
