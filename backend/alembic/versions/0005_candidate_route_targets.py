"""bind unified-model candidates and logs to connection and node targets

Revision ID: 0005_candidate_route_targets
Revises: 0004_provider_routing_foundations
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_candidate_route_targets"
down_revision = "0004_provider_routing_foundations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unified_model_candidates") as batch:
        batch.add_column(sa.Column("provider_connection_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("provider_node_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_candidates_connection", "provider_connections", ["provider_connection_id"], ["id"])
        batch.create_foreign_key("fk_candidates_node", "provider_nodes", ["provider_node_id"], ["id"])
        batch.create_index("ix_unified_model_candidates_provider_connection_id", ["provider_connection_id"])
        batch.create_index("ix_unified_model_candidates_provider_node_id", ["provider_node_id"])
    with op.batch_alter_table("request_logs") as batch:
        batch.add_column(sa.Column("provider_connection_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("provider_node_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_request_logs_connection", "provider_connections", ["provider_connection_id"], ["id"])
        batch.create_foreign_key("fk_request_logs_node", "provider_nodes", ["provider_node_id"], ["id"])
        batch.create_index("ix_request_logs_provider_connection_id", ["provider_connection_id"])
        batch.create_index("ix_request_logs_provider_node_id", ["provider_node_id"])


def downgrade() -> None:
    with op.batch_alter_table("request_logs") as batch:
        batch.drop_index("ix_request_logs_provider_node_id")
        batch.drop_index("ix_request_logs_provider_connection_id")
        batch.drop_constraint("fk_request_logs_node", type_="foreignkey")
        batch.drop_constraint("fk_request_logs_connection", type_="foreignkey")
        batch.drop_column("provider_node_id")
        batch.drop_column("provider_connection_id")
    with op.batch_alter_table("unified_model_candidates") as batch:
        batch.drop_index("ix_unified_model_candidates_provider_node_id")
        batch.drop_index("ix_unified_model_candidates_provider_connection_id")
        batch.drop_constraint("fk_candidates_node", type_="foreignkey")
        batch.drop_constraint("fk_candidates_connection", type_="foreignkey")
        batch.drop_column("provider_node_id")
        batch.drop_column("provider_connection_id")
