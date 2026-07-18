"""add pricing source provenance

Revision ID: 0010_model_pricing_sources
Revises: 0009_webdav_sync_logs
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_model_pricing_sources"
down_revision = "0009_webdav_sync_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_pricing",
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual"),
    )
    op.add_column("model_pricing", sa.Column("source_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("model_pricing", "source_url")
    op.drop_column("model_pricing", "source")
