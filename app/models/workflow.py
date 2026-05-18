"""
Workflow Automation Models

This module contains SQLAlchemy models for managing onboarding and offboarding
workflow checklists generated from job role mappings.
"""

from datetime import datetime, timezone, date
from typing import Dict, Any, List, Optional
from app.database import db
from app.models.base import BaseModel, TimestampMixin


class Workflow(BaseModel, TimestampMixin):
    """Model for onboarding/offboarding workflow checklists."""

    __tablename__ = "workflows"

    workflow_type = db.Column(
        db.String(20), nullable=False, index=True
    )  # "onboarding" / "offboarding"
    status = db.Column(
        db.String(20), nullable=False, default="active", index=True
    )  # "active" / "completed" / "cancelled"
    employee_name = db.Column(db.String(255), nullable=False)
    employee_email = db.Column(
        db.String(255), index=True
    )  # nullable for net-new hires (D-03)
    job_code = db.Column(db.String(50), nullable=False, index=True)
    job_title = db.Column(db.String(255))
    created_by = db.Column(db.String(255), nullable=False, index=True)
    completed_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    items = db.relationship(
        "WorkflowItem",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowItem.sort_order",
    )

    def __repr__(self) -> str:
        return f"<Workflow {self.workflow_type} for {self.employee_name} ({self.status})>"

    @classmethod
    def get_active_workflows(cls) -> List["Workflow"]:
        """Get all active workflows ordered by creation date descending."""
        return (
            cls.query.filter_by(status="active")
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def get_completed_workflows(cls) -> List["Workflow"]:
        """Get all completed workflows ordered by completion date descending."""
        return (
            cls.query.filter_by(status="completed")
            .order_by(cls.completed_at.desc())
            .all()
        )

    @property
    def progress(self) -> Dict[str, Any]:
        """Return progress summary for this workflow.

        Returns:
            Dict with total, completed, pending, and percent keys.
        """
        total = len(self.items)
        completed = sum(
            1 for item in self.items if item.status in ("completed", "skipped")
        )
        pending = sum(1 for item in self.items if item.status == "pending")
        percent = int((completed / total) * 100) if total > 0 else 0
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "percent": percent,
        }

    @property
    def overdue_count(self) -> int:
        """Return the count of overdue pending items."""
        today = date.today()
        return sum(
            1
            for item in self.items
            if item.status == "pending"
            and item.due_date is not None
            and item.due_date < today
        )


class WorkflowItem(BaseModel, TimestampMixin):
    """Model for individual checklist items within a workflow."""

    __tablename__ = "workflow_items"

    workflow_id = db.Column(
        db.Integer, db.ForeignKey("workflows.id"), nullable=False, index=True
    )
    item_text = db.Column(
        db.String(500), nullable=False
    )  # denormalized copy (RESEARCH pitfall 4)
    item_source = db.Column(
        db.String(50), nullable=False
    )  # "role_mapping" / "standard_offboarding"
    source_detail = db.Column(
        db.String(255)
    )  # e.g. "keystone.TellerRole (required)"
    action_type = db.Column(
        db.String(20), nullable=False
    )  # "add" / "remove" / "action"
    system_name = db.Column(db.String(100))
    role_name = db.Column(db.String(255))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(
        db.String(20), nullable=False, default="pending", index=True
    )  # "pending" / "completed" / "skipped"
    completed_by = db.Column(db.String(255))
    completed_at = db.Column(db.DateTime(timezone=True))
    skip_reason = db.Column(db.Text)
    due_date = db.Column(db.Date)

    # Relationships
    workflow = db.relationship("Workflow", back_populates="items")

    def __repr__(self) -> str:
        return f"<WorkflowItem {self.item_text[:40]} ({self.status})>"

    @property
    def is_overdue(self) -> bool:
        """Check if this pending item is past its due date."""
        return (
            self.status == "pending"
            and self.due_date is not None
            and self.due_date < date.today()
        )


class StandardOffboardingItem(BaseModel, TimestampMixin):
    """Model for reusable standard offboarding checklist items.

    These items are appended to every offboarding workflow in addition
    to the role-based items derived from job role mappings.
    """

    __tablename__ = "standard_offboarding_items"

    item_text = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_by = db.Column(db.String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<StandardOffboardingItem {self.item_text[:40]}>"

    @classmethod
    def get_all_active(cls) -> List["StandardOffboardingItem"]:
        """Get all active standard offboarding items ordered by sort_order."""
        return cls.query.filter_by(is_active=True).order_by(cls.sort_order).all()
