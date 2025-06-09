from typing import Optional, List, Dict, Any
from app.database import db
from .base import AuditableModel


class ErrorLog(AuditableModel):
    """Error log model for tracking application errors"""

    __tablename__ = "error_log"

    # AuditableModel provides: id, created_at, updated_at, user_email, user_agent,
    # ip_address, session_id, success, message, additional_data

    # Keep timestamp for backward compatibility
    timestamp = db.synonym("created_at")

    # Error-specific fields
    error_type = db.Column(db.String(100), nullable=False, index=True)
    error_message = db.synonym("message")  # Map to base class field
    stack_trace = db.Column(db.Text)
    request_path = db.Column(db.String(500))
    request_method = db.Column(db.String(10))
    request_data = db.synonym("additional_data")  # Map to base class field
    severity = db.Column(db.String(20), default="ERROR", index=True)

    def __repr__(self):
        return f"<ErrorLog {self.id}: {self.error_type} at {self.timestamp}>"

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        # Use base class to_dict
        data = super().to_dict(exclude)

        # Ensure timestamp alias is included
        data["timestamp"] = data.get("created_at")

        return data

    @classmethod
    def log_error(cls, error_type, error_message, **kwargs):
        """Log an error"""
        log = cls(
            error_type=error_type,
            message=error_message,  # Use base class field
            stack_trace=kwargs.get("stack_trace"),
            user_email=kwargs.get("user_email"),
            request_path=kwargs.get("request_path"),
            request_method=kwargs.get("request_method"),
            additional_data=kwargs.get("request_data"),  # Use base class field
            ip_address=kwargs.get("ip_address"),
            user_agent=kwargs.get("user_agent"),
            severity=kwargs.get("severity", "ERROR"),
            success=False,  # Errors are always failures
        )
        return log.save()
