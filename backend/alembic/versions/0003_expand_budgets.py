"""expand budgets

Revision ID: 0003_expand_budgets
Revises: 0002_expand_api_tokens
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_expand_budgets"
down_revision = "0002_expand_api_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("budgets", sa.Column("name", sa.String(128), nullable=True))
    op.add_column("budgets", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("budgets", sa.Column("spent_amount", sa.Float(), nullable=False, server_default="0"))
    op.add_column("budgets", sa.Column("alert_threshold_percent", sa.Integer(), nullable=False, server_default="80"))
    op.execute("UPDATE budgets SET name = scope || ' budget' WHERE name IS NULL")


def downgrade() -> None:
    op.drop_column("budgets", "alert_threshold_percent")
    op.drop_column("budgets", "spent_amount")
    op.drop_column("budgets", "enabled")
    op.drop_column("budgets", "name")
