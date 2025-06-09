"""Enhanced User model with base classes and proper relationships."""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import relationship
from app.database import db
from app.models.base import BaseModel, TimestampMixin


class User(BaseModel, TimestampMixin):
    """Enhanced user model with proper relationships."""

    __tablename__ = "users"

    # Role constants
    ROLE_VIEWER = "viewer"
    ROLE_EDITOR = "editor"
    ROLE_ADMIN = "admin"

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    role = db.Column(db.String(50), nullable=False, default=ROLE_VIEWER, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    last_login = db.Column(db.DateTime, index=True)
    created_by = db.Column(db.String(255))
    updated_by = db.Column(db.String(255))

    # Relationships with explicit lazy loading strategies
    sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",  # Default behavior, load on access
    )
    notes = relationship(
        "UserNote",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",  # Default behavior, load on access
    )

    @classmethod
    def get_by_email(cls, email: str) -> Optional["User"]:
        """Get user by email address."""
        return cls.query.filter_by(email=email.lower().strip()).first()

    @classmethod
    def get_by_role(cls, role: str, active_only: bool = True) -> List["User"]:
        """Get all users with specific role."""
        query = cls.query.filter_by(role=role)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.all()

    @classmethod
    def get_all_active(cls) -> List["User"]:
        """Get all active users."""
        return cls.query.filter_by(is_active=True).order_by(cls.email).all()

    @classmethod
    def update_user_role(
        cls, email: str, new_role: str, updated_by: str
    ) -> Optional["User"]:
        """Update user role."""
        user = cls.get_by_email(email)
        if user:
            user.role = new_role
            user.updated_by = updated_by
            return user.save()
        return None

    @classmethod
    def deactivate_user(cls, email: str, updated_by: str) -> Optional["User"]:
        """Deactivate a user (soft delete)."""
        user = cls.get_by_email(email)
        if user:
            user.updated_by = updated_by
            return user.deactivate()
        return None

    @classmethod
    def create_user(
        cls, email: str, role: str = ROLE_VIEWER, created_by: str = "system"
    ) -> "User":
        """Create a new user."""
        user = cls(
            email=email.lower().strip(),
            role=role,
            created_by=created_by,
            is_active=True,
        )
        return user.save()

    def update_last_login(self) -> "User":
        """Update last login timestamp."""
        self.last_login = datetime.now(timezone.utc)
        return self.save()

    def deactivate(self) -> "User":
        """Deactivate the user."""
        self.is_active = False
        return self.save()

    def activate(self) -> "User":
        """Activate the user."""
        self.is_active = True
        return self.save()

    def change_role(self, new_role: str) -> "User":
        """Change user role."""
        self.role = new_role
        return self.save()

    def get_active_sessions(self):
        """Get active sessions for this user."""
        from app.models.session import UserSession

        return (
            UserSession.query.filter_by(user_id=self.id, is_active=True)
            .filter(UserSession.expires_at > datetime.now(timezone.utc))
            .all()
        )

    def get_recent_notes(self, limit: int = 10):
        """Get recent notes about this user."""
        from app.models.user_note import UserNote

        return (
            UserNote.query.filter_by(user_id=self.id, is_active=True)
            .order_by(UserNote.created_at.desc())
            .limit(limit)
            .all()
        )

    def has_permission(self, required_role: str) -> bool:
        """Check if user has required permission level."""
        role_hierarchy = {
            self.__class__.ROLE_VIEWER: 1,
            self.__class__.ROLE_EDITOR: 2,
            self.__class__.ROLE_ADMIN: 3,
        }

        user_level = role_hierarchy.get(self.role, 0)
        required_level = role_hierarchy.get(required_role, 999)

        return user_level >= required_level and self.is_active

    def to_dict(self, exclude: Optional[List[str]] = None) -> dict:
        """Convert to dictionary with additional computed fields."""
        result = super().to_dict(exclude=exclude)

        # Add computed fields
        result["active_sessions_count"] = len(self.get_active_sessions())
        # Use efficient count query instead of loading all notes
        from app.models.user_note import UserNote

        result["notes_count"] = UserNote.query.filter_by(
            user_id=self.id, is_active=True
        ).count()
        result["display_name"] = self.email.split("@")[0].title()

        return result

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
