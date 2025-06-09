from flask import session as flask_session, request
from typing import Optional, TYPE_CHECKING
import secrets

if TYPE_CHECKING:
    from app.models.session import UserSession


class SessionManager:
    """Handles user session management"""

    def __init__(self):
        self._timeout_minutes = 15  # Default timeout

    def get_current_session(self, user_email: str) -> Optional["UserSession"]:
        """
        Get current session for user

        Args:
            user_email: User's email address

        Returns:
            UserSession if valid session exists, None otherwise
        """
        from app.models.session import UserSession
        from datetime import datetime, timezone, timedelta

        session_id = flask_session.get("session_id")
        user_session = None

        # First try to get session by stored session_id
        if session_id:
            user_session = UserSession.query.get(session_id)
            if user_session and user_session.user_email != user_email:
                # Session doesn't match user
                user_session = None
                flask_session.clear()

        # If no session found via Flask session, try to find recent active session for user
        if not user_session:
            recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
            user_session = (
                UserSession.query.filter(
                    UserSession.user_email == user_email,
                    UserSession.is_active.is_(True),
                    UserSession.expires_at > datetime.now(timezone.utc),
                    UserSession.last_activity > recent_cutoff,
                )
                .order_by(UserSession.last_activity.desc())
                .first()
            )

            if user_session:
                # Restore session ID to Flask session
                flask_session["session_id"] = user_session.id
                flask_session.permanent = True

        if not user_session:
            return None

        if user_session.is_expired() or not user_session.is_active:
            # Session expired or inactive
            user_session.deactivate()
            flask_session.clear()
            return None

        # Update activity timestamp
        user_session.update_activity()
        return user_session  # type: ignore[no-any-return]

    def create_session(
        self, user_id: int, user_email: str, timeout_minutes: Optional[int] = None
    ) -> "UserSession":
        """
        Create new session for user

        Args:
            user_id: User's database ID
            user_email: User's email address
            timeout_minutes: Session timeout in minutes

        Returns:
            New UserSession object
        """
        from app.models.session import UserSession

        if timeout_minutes is not None:
            self._timeout_minutes = timeout_minutes

        new_session_id = secrets.token_urlsafe(32)
        user_session = UserSession.create_session(
            session_id=new_session_id,
            user_id=user_id,
            user_email=user_email,
            timeout_minutes=self._timeout_minutes,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
            user_agent=request.headers.get("User-Agent"),
        )

        # Store session ID in Flask session
        flask_session["session_id"] = user_session.id
        flask_session.permanent = True

        return user_session

    def clear_session(self) -> None:
        """Clear current session"""
        flask_session.clear()

    def get_or_create_session(
        self, user_id: int, user_email: str, timeout_minutes: Optional[int] = None
    ) -> "UserSession":
        """
        Get existing session or create new one

        Args:
            user_id: User's database ID
            user_email: User's email address
            timeout_minutes: Session timeout in minutes

        Returns:
            UserSession object
        """
        # Try to get existing session
        user_session = self.get_current_session(user_email)

        if not user_session:
            # Before creating new session, cleanup ALL old sessions for this user
            self._cleanup_all_user_sessions(user_id, user_email)
            # Create new session
            user_session = self.create_session(user_id, user_email, timeout_minutes)

        return user_session

    def _cleanup_old_user_sessions(self, user_id: int, user_email: str) -> None:
        """
        Clean up old/expired sessions for a user

        Args:
            user_id: User's database ID
            user_email: User's email address
        """
        from app.models.session import UserSession
        from datetime import datetime, timezone, timedelta
        from app.database import db

        try:
            # Deactivate sessions that are expired or very old (over 1 hour inactive)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

            old_sessions = UserSession.query.filter(
                UserSession.user_id == user_id,
                UserSession.user_email == user_email,
                db.or_(
                    UserSession.expires_at < datetime.now(timezone.utc),  # Expired
                    UserSession.last_activity < cutoff_time,  # Very old
                    UserSession.is_active.is_(False),  # Already inactive
                ),
            ).all()

            for session in old_sessions:
                session.deactivate()

            db.session.commit()

        except Exception:
            # Don't let cleanup failures break session creation
            db.session.rollback()

    def _cleanup_all_user_sessions(self, user_id: int, user_email: str) -> None:
        """
        Clean up ALL existing sessions for a user to ensure only one session

        Args:
            user_id: User's database ID
            user_email: User's email address
        """
        from app.models.session import UserSession
        from app.database import db

        try:
            # Deactivate ALL existing sessions for this user
            existing_sessions = UserSession.query.filter(
                UserSession.user_id == user_id,
                UserSession.user_email == user_email,
                UserSession.is_active.is_(True),
            ).all()

            for session in existing_sessions:
                session.deactivate()

            db.session.commit()

        except Exception:
            # Don't let cleanup failures break session creation
            db.session.rollback()
