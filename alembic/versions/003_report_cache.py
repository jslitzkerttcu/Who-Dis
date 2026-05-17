"""report_cache

Revision ID: 003_report_cache
Revises: 002_compliance_polish
Create Date: 2026-05-17

Phase 8 — Reporting: Adds report_cache table for storing aggregated
report data with tiered TTL and staleness detection.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_report_cache"
down_revision: Union[str, None] = "002_compliance_polish"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("cache_key", sa.String(100), nullable=False, index=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("ttl_hours", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "report_type", "cache_key", name="uq_report_cache"
        ),
    )


def downgrade() -> None:
    op.drop_table("report_cache")
