"""add gateway-managed file storage

Revision ID: 0007_stored_files
Revises: 0006_budget_enforcement
"""
from alembic import op
import sqlalchemy as sa


revision = "0007_stored_files"
down_revision = "0006_budget_enforcement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stored_files",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("api_token_id", sa.Integer(), sa.ForeignKey("api_tokens.id"), nullable=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False, server_default="assistants"),
        sa.Column("mime_type", sa.String(256), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="processed"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stored_files_api_token_id", "stored_files", ["api_token_id"])
    op.create_index("ix_stored_files_sha256", "stored_files", ["sha256"])


def downgrade() -> None:
    op.drop_table("stored_files")
