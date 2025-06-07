from datetime import datetime, timedelta
from app.database import db
import secrets


class UserSession(db.Model):  # type: ignore
    """User session tracking"""

    __tablename__ = "user_sessions"

    id = db.Column(db.String(255), primary_key=True)
    user_email = db.Column(db.String(255), nullable=False, index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    warning_shown = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<UserSession {self.id}: {self.user_email}>"

    def is_expired(self):
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()
        db.session.commit()

    def extend_session(self, timeout_minutes=15):
        """Extend session expiration"""
        self.expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        self.last_activity = datetime.utcnow()
        self.warning_shown = False
        db.session.commit()

    def mark_warning_shown(self):
        """Mark that warning has been shown"""
        self.warning_shown = True
        db.session.commit()

    def deactivate(self):
        """Deactivate session"""
        self.is_active = False
        db.session.commit()

    @classmethod
    def create_session(cls, user_email, timeout_minutes=15, **kwargs):
        """Create a new session"""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)

        session = cls(
            id=session_id,
            user_email=user_email,
            ip_address=kwargs.get("ip_address"),
            user_agent=kwargs.get("user_agent"),
            expires_at=expires_at,
        )
        db.session.add(session)
        db.session.commit()
        return session

    @classmethod
    def cleanup_expired(cls):
        """Remove expired sessions"""
        cls.query.filter(cls.expires_at < datetime.utcnow()).delete()
        db.session.commit()
