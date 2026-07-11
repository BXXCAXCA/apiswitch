"""add configurable budget enforcement action

Revision ID: 0006_budget_enforcement
Revises: 0005_candidate_route_targets
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_budget_enforcement"
down_revision = "0005_candidate_route_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("budgets") as batch:
        batch.add_column(sa.Column("enforcement_action", sa.String(32), nullable=False, server_default="warn_only"))


def downgrade() -> None:
    with op.batch_alter_table("budgets") as batch:
        batch.drop_column("enforcement_action")
