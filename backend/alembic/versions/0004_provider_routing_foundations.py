"""provider routing foundations

Revision ID: 0004_provider_routing_foundations
Revises: 0003_expand_budgets
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_provider_routing_foundations"
down_revision = "0003_expand_budgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("auth_type", sa.String(32), nullable=False, server_default="api_key"),
        sa.Column("account_label", sa.String(128), nullable=True),
        sa.Column("credential_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_provider_connections_provider_id", "provider_connections", ["provider_id"])

    op.create_table(
        "provider_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("connection_id", sa.Integer(), sa.ForeignKey("provider_connections.id"), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("region", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("capabilities_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_provider_nodes_provider_id", "provider_nodes", ["provider_id"])
    op.create_index("ix_provider_nodes_connection_id", "provider_nodes", ["connection_id"])

    op.create_table(
        "model_pricing",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=True),
        sa.Column("model_name", sa.String(256), nullable=False),
        sa.Column("input_cost_per_million", sa.Float(), nullable=True),
        sa.Column("output_cost_per_million", sa.Float(), nullable=True),
        sa.Column("cached_input_cost_per_million", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(16), nullable=False, server_default="USD"),
        sa.Column("effective_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_model_pricing_provider_id", "model_pricing", ["provider_id"])
    op.create_index("ix_model_pricing_model_name", "model_pricing", ["model_name"])

    op.create_table(
        "quota_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "provider_connection_id",
            sa.Integer(),
            sa.ForeignKey("provider_connections.id"),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("remaining_requests", sa.Integer(), nullable=True),
        sa.Column("remaining_tokens", sa.Integer(), nullable=True),
        sa.Column("remaining_credit", sa.Float(), nullable=True),
        sa.Column("reset_at", sa.DateTime(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_quota_snapshots_provider_connection_id",
        "quota_snapshots",
        ["provider_connection_id"],
    )
    op.create_index("ix_quota_snapshots_captured_at", "quota_snapshots", ["captured_at"])

    op.create_table(
        "usage_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("api_token_id", sa.Integer(), sa.ForeignKey("api_tokens.id"), nullable=True),
        sa.Column(
            "provider_connection_id",
            sa.Integer(),
            sa.ForeignKey("provider_connections.id"),
            nullable=True,
        ),
        sa.Column("unified_model", sa.String(128), nullable=False),
        sa.Column("upstream_model", sa.String(256), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_usage_history_request_id", "usage_history", ["request_id"])
    op.create_index("ix_usage_history_api_token_id", "usage_history", ["api_token_id"])
    op.create_index(
        "ix_usage_history_provider_connection_id",
        "usage_history",
        ["provider_connection_id"],
    )
    op.create_index("ix_usage_history_unified_model", "usage_history", ["unified_model"])
    op.create_index("ix_usage_history_created_at", "usage_history", ["created_at"])

    op.create_table(
        "session_affinity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_key", sa.String(256), nullable=False, unique=True),
        sa.Column("unified_model_id", sa.Integer(), sa.ForeignKey("unified_models.id"), nullable=False),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("unified_model_candidates.id"),
            nullable=True,
        ),
        sa.Column(
            "provider_connection_id",
            sa.Integer(),
            sa.ForeignKey("provider_connections.id"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_session_affinity_session_key", "session_affinity", ["session_key"])
    op.create_index("ix_session_affinity_unified_model_id", "session_affinity", ["unified_model_id"])
    op.create_index("ix_session_affinity_candidate_id", "session_affinity", ["candidate_id"])
    op.create_index(
        "ix_session_affinity_provider_connection_id",
        "session_affinity",
        ["provider_connection_id"],
    )


def downgrade() -> None:
    op.drop_table("session_affinity")
    op.drop_table("usage_history")
    op.drop_table("quota_snapshots")
    op.drop_table("model_pricing")
    op.drop_table("provider_nodes")
    op.drop_table("provider_connections")
