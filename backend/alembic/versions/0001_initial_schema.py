"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table("providers", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(128), nullable=False), sa.Column("type", sa.String(64), nullable=False), sa.Column("base_url", sa.String(512), nullable=False), sa.Column("api_key_encrypted", sa.Text(), nullable=True), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("timeout_seconds", sa.Integer(), nullable=False), sa.Column("proxy_type", sa.String(32), nullable=True), sa.Column("proxy_url", sa.String(512), nullable=True), *_timestamps())
    op.create_index("ix_providers_name", "providers", ["name"], unique=True)
    op.create_index("ix_providers_type", "providers", ["type"])
    op.create_table("provider_models", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=False), sa.Column("model_name", sa.String(256), nullable=False), sa.Column("capabilities_json", sa.JSON(), nullable=True), sa.Column("enabled", sa.Boolean(), nullable=False), *_timestamps())
    op.create_table("unified_models", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(128), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("capabilities_json", sa.JSON(), nullable=True), *_timestamps())
    op.create_index("ix_unified_models_name", "unified_models", ["name"], unique=True)
    op.create_table("unified_model_candidates", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("unified_model_id", sa.Integer(), sa.ForeignKey("unified_models.id"), nullable=False), sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=False), sa.Column("upstream_model", sa.String(256), nullable=False), sa.Column("manual_priority", sa.Integer(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("capabilities_json", sa.JSON(), nullable=True), *_timestamps())
    op.create_table("provider_health", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("unified_model_candidates.id"), nullable=False), sa.Column("success_count", sa.Integer(), nullable=False), sa.Column("failure_count", sa.Integer(), nullable=False), sa.Column("consecutive_failures", sa.Integer(), nullable=False), sa.Column("avg_latency_ms", sa.Float(), nullable=True), sa.Column("p50_latency_ms", sa.Float(), nullable=True), sa.Column("p95_latency_ms", sa.Float(), nullable=True), sa.Column("first_token_latency_ms", sa.Float(), nullable=True), sa.Column("last_success_at", sa.DateTime(), nullable=True), sa.Column("last_failure_at", sa.DateTime(), nullable=True), sa.Column("last_failure_reason", sa.Text(), nullable=True), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_table("circuit_breakers", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("unified_model_candidates.id"), nullable=False), sa.Column("state", sa.String(32), nullable=False), sa.Column("opened_at", sa.DateTime(), nullable=True), sa.Column("half_open_at", sa.DateTime(), nullable=True), sa.Column("failure_threshold", sa.Integer(), nullable=False), sa.Column("cooldown_seconds", sa.Integer(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_table("request_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("request_id", sa.String(128), nullable=False), sa.Column("started_at", sa.DateTime(), nullable=False), sa.Column("finished_at", sa.DateTime(), nullable=True), sa.Column("inbound_protocol", sa.String(64), nullable=False), sa.Column("unified_model", sa.String(128), nullable=False), sa.Column("final_provider", sa.String(128), nullable=True), sa.Column("final_upstream_model", sa.String(256), nullable=True), sa.Column("success", sa.Boolean(), nullable=False), sa.Column("error_type", sa.String(128), nullable=True), sa.Column("error_message", sa.Text(), nullable=True), sa.Column("retry_chain_json", sa.JSON(), nullable=True), sa.Column("input_tokens", sa.Integer(), nullable=True), sa.Column("output_tokens", sa.Integer(), nullable=True), sa.Column("estimated_cost", sa.Float(), nullable=True), sa.Column("latency_ms", sa.Float(), nullable=True), sa.Column("first_token_latency_ms", sa.Float(), nullable=True), sa.Column("cache_hit", sa.Boolean(), nullable=False), sa.Column("debug_request_body_encrypted", sa.Text(), nullable=True), sa.Column("debug_response_body_encrypted", sa.Text(), nullable=True))
    op.create_index("ix_request_logs_request_id", "request_logs", ["request_id"], unique=True)
    op.create_table("api_tokens", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(128), nullable=False), sa.Column("token_hash", sa.String(256), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), *_timestamps())
    op.create_table("budgets", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("scope", sa.String(64), nullable=False), sa.Column("scope_id", sa.String(128), nullable=True), sa.Column("monthly_limit", sa.Float(), nullable=True), sa.Column("currency", sa.String(16), nullable=False), *_timestamps())
    op.create_table("file_cache", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("cache_key", sa.String(128), nullable=False), sa.Column("parse_strategy", sa.String(64), nullable=False), sa.Column("parser_version", sa.String(64), nullable=False), sa.Column("content_json", sa.JSON(), nullable=True), *_timestamps())
    op.create_table("embedding_cache", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("cache_key", sa.String(128), nullable=False), sa.Column("provider", sa.String(128), nullable=False), sa.Column("model", sa.String(256), nullable=False), sa.Column("vector_json", sa.JSON(), nullable=True), *_timestamps())
    op.create_table("webdav_profiles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(128), nullable=False), sa.Column("url", sa.String(512), nullable=False), sa.Column("username", sa.String(256), nullable=True), sa.Column("password_encrypted", sa.Text(), nullable=True), sa.Column("enabled", sa.Boolean(), nullable=False), *_timestamps())
    op.create_table("agent_configs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("agent_type", sa.String(64), nullable=False), sa.Column("config_path", sa.String(1024), nullable=True), sa.Column("last_backup_path", sa.String(1024), nullable=True), sa.Column("settings_json", sa.JSON(), nullable=True), *_timestamps())
    op.create_table("settings", sa.Column("key", sa.String(128), primary_key=True), sa.Column("value_json", sa.JSON(), nullable=True), sa.Column("updated_at", sa.DateTime(), nullable=False))


def downgrade() -> None:
    for table in ["settings", "agent_configs", "webdav_profiles", "embedding_cache", "file_cache", "budgets", "api_tokens", "request_logs", "circuit_breakers", "provider_health", "unified_model_candidates", "unified_models", "provider_models", "providers"]:
        op.drop_table(table)
