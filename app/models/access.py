from typing import Optional, List, Dict, Any
from app.database import db
from .base import AuditableModel


class AccessAttempt(AuditableModel):
    """Access attempt model for security monitoring"""

    __tablename__ = "access_attempts"

    # AuditableModel provides: id, created_at, updated_at, user_email, user_agent,
    # ip_address, session_id, success, message, additional_data

    # Keep timestamp for backward compatibility
    timestamp = db.synonym("created_at")

    # Access-specific fields
    requested_path = db.Column(db.String(500))
    access_granted = db.synonym("success")  # Map to base class field
    denial_reason = db.synonym("message")  # Map to base class field
    auth_method = db.Column(db.String(50))

    def __repr__(self):
        return f"<AccessAttempt {self.id}: {self.user_email or 'anonymous'} - {'granted' if self.success else 'denied'}>"

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        # Use base class to_dict
        data = super().to_dict(exclude)

        # Ensure alias fields are included with their familiar names
        data["timestamp"] = data.get("created_at")
        data["access_granted"] = data.get("success")
        data["denial_reason"] = data.get("message")

        return data

    @classmethod
    def log_attempt(cls, ip_address, access_granted, **kwargs):
        """Log an access attempt"""
        attempt = cls(
            ip_address=ip_address,
            success=access_granted,  # Use base class field
            user_email=kwargs.get("user_email"),
            user_agent=kwargs.get("user_agent"),
            requested_path=kwargs.get("requested_path"),
            message=kwargs.get("denial_reason"),  # Use base class field
            auth_method=kwargs.get("auth_method"),
        )
        return attempt.save()
