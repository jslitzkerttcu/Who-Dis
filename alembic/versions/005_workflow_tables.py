"""workflow_tables

Revision ID: 005_workflow_tables
Revises: 004_external_api_tokens
Create Date: 2026-05-18

Phase 11 -- Workflow Automation: Adds workflows, workflow_items, and
standard_offboarding_items tables for onboarding/offboarding checklists.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_workflow_tables"
down_revision: Union[str, None] = "004_external_api_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("employee_name", sa.String(255), nullable=False),
        sa.Column("employee_email", sa.String(255), nullable=True),
        sa.Column("job_code", sa.String(50), nullable=False),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflows_status", "workflows", ["status"])
    op.create_index("ix_workflows_workflow_type", "workflows", ["workflow_type"])
    op.create_index("ix_workflows_employee_email", "workflows", ["employee_email"])
    op.create_index("ix_workflows_job_code", "workflows", ["job_code"])
    op.create_index("ix_workflows_created_by", "workflows", ["created_by"])

    op.create_table(
        "workflow_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("workflows.id"),
            nullable=False,
        ),
        sa.Column("item_text", sa.String(500), nullable=False),
        sa.Column("item_source", sa.String(50), nullable=False),
        sa.Column("source_detail", sa.String(255), nullable=True),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("system_name", sa.String(100), nullable=True),
        sa.Column("role_name", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_by", sa.String(255), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_items_workflow_id", "workflow_items", ["workflow_id"])
    op.create_index("ix_workflow_items_status", "workflow_items", ["status"])

    op.create_table(
        "standard_offboarding_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_text", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_standard_offboarding_items_is_active",
        "standard_offboarding_items",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_standard_offboarding_items_is_active",
        table_name="standard_offboarding_items",
    )
    op.drop_table("standard_offboarding_items")

    op.drop_index("ix_workflow_items_status", table_name="workflow_items")
    op.drop_index("ix_workflow_items_workflow_id", table_name="workflow_items")
    op.drop_table("workflow_items")

    op.drop_index("ix_workflows_created_by", table_name="workflows")
    op.drop_index("ix_workflows_job_code", table_name="workflows")
    op.drop_index("ix_workflows_employee_email", table_name="workflows")
    op.drop_index("ix_workflows_workflow_type", table_name="workflows")
    op.drop_index("ix_workflows_status", table_name="workflows")
    op.drop_table("workflows")
