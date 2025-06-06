from datetime import datetime
from app.database import db


class AccessAttempt(db.Model):  # type: ignore
    """Access attempt model for security monitoring"""

    __tablename__ = "access_attempts"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    user_email = db.Column(db.String(255), index=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    user_agent = db.Column(db.Text)
    requested_path = db.Column(db.String(500))
    access_granted = db.Column(db.Boolean, nullable=False, index=True)
    denial_reason = db.Column(db.String(255))
    auth_method = db.Column(db.String(50))

    def __repr__(self):
        return f"<AccessAttempt {self.id}: {self.user_email or 'anonymous'} - {'granted' if self.access_granted else 'denied'}>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user_email": self.user_email,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "requested_path": self.requested_path,
            "access_granted": self.access_granted,
            "denial_reason": self.denial_reason,
            "auth_method": self.auth_method,
        }

    @classmethod
    def log_attempt(cls, ip_address, access_granted, **kwargs):
        """Log an access attempt"""
        attempt = cls(
            ip_address=ip_address,
            access_granted=access_granted,
            user_email=kwargs.get("user_email"),
            user_agent=kwargs.get("user_agent"),
            requested_path=kwargs.get("requested_path"),
            denial_reason=kwargs.get("denial_reason"),
            auth_method=kwargs.get("auth_method"),
        )
        db.session.add(attempt)
        db.session.commit()
        return attempt
