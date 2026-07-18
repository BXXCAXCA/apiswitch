"""add WebDAV sync logs

Revision ID: 0009_webdav_sync_logs
Revises: 0008_batch_jobs
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_webdav_sync_logs"
down_revision = "0008_batch_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webdav_sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("webdav_profiles.id"), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("conflict_strategy", sa.String(32), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_webdav_sync_logs_profile_id", "webdav_sync_logs", ["profile_id"])
    op.create_index("ix_webdav_sync_logs_created_at", "webdav_sync_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("webdav_sync_logs")
