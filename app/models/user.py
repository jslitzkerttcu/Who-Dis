from datetime import datetime
from app.database import db
from typing import Optional, List


class User(db.Model):  # type: ignore
    """User model for authentication and authorization"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    role = db.Column(db.String(50), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_by = db.Column(db.String(255))
    last_login = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    # Role constants
    ROLE_VIEWER = "viewer"
    ROLE_EDITOR = "editor"
    ROLE_ADMIN = "admin"

    # Role hierarchy
    ROLE_HIERARCHY = {ROLE_VIEWER: 1, ROLE_EDITOR: 2, ROLE_ADMIN: 3}

    def __repr__(self):
        return f"<User {self.email}: {self.role}>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "notes": self.notes,
        }

    def has_role(self, required_role: str) -> bool:
        """Check if user has at least the required role level"""
        if not self.is_active:
            return False

        user_level = self.ROLE_HIERARCHY.get(self.role, 0)
        required_level = self.ROLE_HIERARCHY.get(required_role, 0)

        return user_level >= required_level

    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()

    @classmethod
    def get_by_email(cls, email: str) -> Optional["User"]:
        """Get user by email"""
        return cls.query.filter_by(email=email.lower(), is_active=True).first()

    @classmethod
    def get_all_active(cls) -> List["User"]:
        """Get all active users"""
        return cls.query.filter_by(is_active=True).order_by(cls.email).all()

    @classmethod
    def get_by_role(cls, role: str) -> List["User"]:
        """Get all users with a specific role"""
        return cls.query.filter_by(role=role, is_active=True).order_by(cls.email).all()

    @classmethod
    def create_user(
        cls, email: str, role: str, created_by: str, notes: Optional[str] = None
    ) -> "User":
        """Create a new user"""
        user = cls(email=email.lower(), role=role, created_by=created_by, notes=notes)
        db.session.add(user)
        db.session.commit()
        return user

    @classmethod
    def update_user_role(
        cls, email: str, new_role: str, updated_by: str
    ) -> Optional["User"]:
        """Update user's role"""
        user = cls.get_by_email(email)
        if user:
            user.role = new_role
            user.updated_by = updated_by
            db.session.commit()
        return user

    @classmethod
    def deactivate_user(cls, email: str, updated_by: str) -> Optional["User"]:
        """Deactivate a user"""
        user = cls.get_by_email(email)
        if user:
            user.is_active = False
            user.updated_by = updated_by
            db.session.commit()
        return user

    @classmethod
    def reactivate_user(cls, email: str, updated_by: str) -> Optional["User"]:
        """Reactivate a user"""
        user = cls.query.filter_by(email=email.lower()).first()
        if user:
            user.is_active = True
            user.updated_by = updated_by
            db.session.commit()
        return user

    @classmethod
    def get_role_counts(cls) -> dict:
        """Get count of users by role"""
        counts = {}
        for role in [cls.ROLE_VIEWER, cls.ROLE_EDITOR, cls.ROLE_ADMIN]:
            counts[role] = cls.query.filter_by(role=role, is_active=True).count()
        return counts
