"""compliance_polish

Revision ID: 002_compliance_polish
Revises: 001_baseline_from_live_schema
Create Date: 2026-05-17

Phase 7 — Compliance Polish: Adds job_runs and sync_metadata tables,
and adds checked_count column to compliance_check_runs.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_compliance_polish"
down_revision: Union[str, None] = "001_baseline_from_live_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add checked_count to compliance_check_runs
    op.add_column(
        "compliance_check_runs",
        sa.Column("checked_count", sa.Integer(), server_default="0"),
    )

    # Create sync_metadata table
    op.create_table(
        "sync_metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sync_type", sa.String(50), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("last_error_category", sa.String(100), nullable=True),
        sa.Column("total_records_synced", sa.Integer(), server_default="0"),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sync_type"),
    )
    op.create_index("ix_sync_metadata_sync_type", "sync_metadata", ["sync_type"])

    # Create job_runs table
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(100), nullable=False),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), server_default="running"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(255), server_default="system"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_job_runs_run_id", "job_runs", ["run_id"])
    op.create_index("ix_job_runs_job_name", "job_runs", ["job_name"])
    op.create_index("ix_job_runs_status", "job_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_index("ix_job_runs_job_name", table_name="job_runs")
    op.drop_index("ix_job_runs_run_id", table_name="job_runs")
    op.drop_table("job_runs")

    op.drop_index("ix_sync_metadata_sync_type", table_name="sync_metadata")
    op.drop_table("sync_metadata")

    op.drop_column("compliance_check_runs", "checked_count")
