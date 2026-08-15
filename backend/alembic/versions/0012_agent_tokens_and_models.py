"""bind each Agent config to an API token and multiple unified models

Revision ID: 0012_agent_tokens_and_models
Revises: 0011_api_token_unified_models
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_agent_tokens_and_models"
down_revision = "0011_api_token_unified_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_configs", sa.Column("model_ids_json", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column(
        "agent_configs",
        sa.Column("api_token_id", sa.Integer(), sa.ForeignKey("api_tokens.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_agent_configs_api_token_id", "agent_configs", ["api_token_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_configs_api_token_id", table_name="agent_configs")
    op.drop_column("agent_configs", "api_token_id")
    op.drop_column("agent_configs", "model_ids_json")
