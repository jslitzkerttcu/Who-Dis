"""external_api_tokens

Revision ID: 004_external_api_tokens
Revises: 003_report_cache
Create Date: 2026-05-18

Phase 10 -- REST API: Adds external_api_tokens table for bearer
token authentication against the public API.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_external_api_tokens"
down_revision: Union[str, None] = "003_report_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_prefix", sa.String(8), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column(
            "is_revoked", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "usage_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_external_api_tokens_token_hash",
        "external_api_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_external_api_tokens_is_revoked",
        "external_api_tokens",
        ["is_revoked"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_api_tokens_is_revoked",
        table_name="external_api_tokens",
    )
    op.drop_index(
        "ix_external_api_tokens_token_hash",
        table_name="external_api_tokens",
    )
    op.drop_table("external_api_tokens")
