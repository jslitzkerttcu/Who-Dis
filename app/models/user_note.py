"""Enhanced UserNote model with base classes and relationships."""

from typing import Optional, List
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from app.database import db
from app.models.base import BaseModel, TimestampMixin


class UserNote(BaseModel, TimestampMixin):
    """User notes with proper relationships."""

    __tablename__ = "user_notes"

    # Foreign key to users table
    user_id = db.Column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Note content and metadata
    created_by = db.Column(
        db.String(100), nullable=False, index=True
    )  # Match DB VARCHAR(100)
    note = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, index=True)

    # Context to separate admin notes from search notes
    context = db.Column(
        db.String(20), nullable=False, default="admin", index=True
    )  # 'admin' or 'search'

    # Relationships
    user = relationship("User", back_populates="notes")

    @classmethod
    def create_note(
        cls,
        user_id: int,
        note_text: str,
        created_by: str,
        context: str = "admin",
    ) -> "UserNote":
        """Create a new note for a user."""
        note = cls(
            user_id=user_id,
            note=note_text.strip(),
            created_by=created_by,
            context=context,
            is_active=True,
        )
        return note.save()

    @classmethod
    def get_user_notes(
        cls, user_id: int, context: str = None, active_only: bool = True
    ) -> List["UserNote"]:
        """Get notes for a specific user, optionally filtered by context."""
        query = cls.query.filter_by(user_id=user_id)

        if context:
            query = query.filter_by(context=context)

        if active_only:
            query = query.filter_by(is_active=True)

        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_notes_by_creator(
        cls, created_by: str, active_only: bool = True
    ) -> List["UserNote"]:
        """Get all notes created by a specific user."""
        query = cls.query.filter_by(created_by=created_by)

        if active_only:
            query = query.filter_by(is_active=True)

        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def search_notes(
        cls, search_text: str, user_id: int = None, context: str = None
    ) -> List["UserNote"]:
        """Search notes by text content."""
        query = cls.query.filter(cls.note.ilike(f"%{search_text}%"), cls.is_active)

        if user_id:
            query = query.filter_by(user_id=user_id)

        if context:
            query = query.filter_by(context=context)

        return query.order_by(cls.created_at.desc()).all()

    def deactivate(self) -> "UserNote":
        """Deactivate (soft delete) the note."""
        self.is_active = False
        return self.save()

    def update_note(self, note_text: str) -> "UserNote":
        """Update note content and metadata."""
        self.note = note_text.strip()
        return self.save()

    def get_preview(self, max_length: int = 100) -> str:
        """Get a preview of the note text."""
        if len(self.note) <= max_length:
            return self.note
        return self.note[:max_length].rsplit(" ", 1)[0] + "..."

    def to_dict(self, exclude: Optional[List[str]] = None) -> dict:
        """Convert to dictionary with note-specific fields."""
        result = super().to_dict(exclude=exclude)

        # Add computed fields
        result["preview"] = self.get_preview()
        result["character_count"] = len(self.note)
        result["context"] = self.context

        # Include user email for display
        if self.user:
            result["user_email"] = self.user.email

        return result

    def __repr__(self):
        preview = self.get_preview(50)
        return f'<UserNote for user_id={self.user_id}: "{preview}">'
