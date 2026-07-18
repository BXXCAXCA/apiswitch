"""add API token unified-model allow list

Revision ID: 0011_api_token_unified_models
Revises: 0010_model_pricing_sources
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_api_token_unified_models"
down_revision = "0010_model_pricing_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_token_unified_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_token_id", sa.Integer(), sa.ForeignKey("api_tokens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unified_model_id", sa.Integer(), sa.ForeignKey("unified_models.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("api_token_id", "unified_model_id", name="uq_api_token_unified_model"),
    )
    op.create_index("ix_api_token_unified_models_api_token_id", "api_token_unified_models", ["api_token_id"])
    op.create_index("ix_api_token_unified_models_unified_model_id", "api_token_unified_models", ["unified_model_id"])


def downgrade() -> None:
    op.drop_table("api_token_unified_models")
