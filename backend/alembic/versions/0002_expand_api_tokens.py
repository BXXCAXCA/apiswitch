"""expand api tokens

Revision ID: 0002_expand_api_tokens
Revises: 0001_initial_schema
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_expand_api_tokens"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_tokens", sa.Column("token_prefix", sa.String(32), nullable=True))
    op.add_column("api_tokens", sa.Column("scopes_json", sa.JSON(), nullable=True))
    op.add_column("api_tokens", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("api_tokens", sa.Column("last_used_at", sa.DateTime(), nullable=True))
    op.create_index("ix_api_tokens_token_prefix", "api_tokens", ["token_prefix"])
    op.execute("UPDATE api_tokens SET token_prefix = substr(token_hash, 1, 12) WHERE token_prefix IS NULL")


def downgrade() -> None:
    op.drop_index("ix_api_tokens_token_prefix", table_name="api_tokens")
    op.drop_column("api_tokens", "last_used_at")
    op.drop_column("api_tokens", "expires_at")
    op.drop_column("api_tokens", "scopes_json")
    op.drop_column("api_tokens", "token_prefix")
