"""allow Agent configs to select an existing API token

Revision ID: 0013_agent_token_selection
Revises: 0012_agent_tokens_and_models
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_agent_token_selection"
down_revision = "0012_agent_tokens_and_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_configs",
        sa.Column("api_token_mode", sa.String(length=16), nullable=False, server_default="auto"),
    )


def downgrade() -> None:
    op.drop_column("agent_configs", "api_token_mode")
