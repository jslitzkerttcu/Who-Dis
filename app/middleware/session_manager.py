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

        session_id = flask_session.get("session_id")
        if not session_id:
            return None

        user_session = UserSession.query.get(session_id)
        if not user_session or user_session.user_email != user_email:
            # Session doesn't exist or doesn't match user
            flask_session.clear()
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
            # Create new session
            user_session = self.create_session(user_id, user_email, timeout_minutes)

        return user_session
