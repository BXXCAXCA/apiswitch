"""Schema generation 2: the APISwitch business model.

There intentionally are no Connection or Node tables in this module.  A provider
instance owns its credentials and an upstream model belongs directly to that
instance.  Keeping this boundary in the ORM prevents old UI/API paths from
accidentally re-entering the new request pipeline.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apiswitch.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SchemaMetadata(Base):
    __tablename__ = "schema_metadata"
    generation: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reset_from_backup: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class ProviderInstance(Base, TimestampMixin):
    __tablename__ = "provider_instances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    template_key: Mapped[str] = mapped_column(String(96), index=True)
    protocol_type: Mapped[str] = mapped_column(String(64), index=True)
    base_url: Mapped[str] = mapped_column(String(1024))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_encrypted_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    custom_headers_encrypted_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    proxy_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    proxy_url_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="unverified")
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    models: Mapped[list["UpstreamModel"]] = relationship(back_populates="provider_instance", cascade="all, delete-orphan")


class UpstreamModel(Base, TimestampMixin):
    __tablename__ = "upstream_models"
    __table_args__ = (UniqueConstraint("provider_instance_id", "model_id", name="uq_upstream_instance_model"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_instance_id: Mapped[int] = mapped_column(ForeignKey("provider_instances.id"), index=True)
    model_id: Mapped[str] = mapped_column(String(256), index=True)
    display_name: Mapped[str] = mapped_column(String(256))
    input_capabilities_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    output_capabilities_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    cached_input_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(16), default="USD")
    pricing_source: Mapped[str] = mapped_column(String(64), default="manual")
    pricing_effective_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tags_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    remote_status: Mapped[str] = mapped_column(String(16), default="unknown")
    remote_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    provider_instance: Mapped[ProviderInstance] = relationship(back_populates="models")


class UnifiedModel(Base, TimestampMixin):
    __tablename__ = "unified_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_capabilities_json: Mapped[dict[str, list[str]] | None] = mapped_column(JSON, nullable=True)
    enabled_protocols_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    routing_mode: Mapped[str] = mapped_column(String(32), default="static")
    combo_strategy: Mapped[str] = mapped_column(String(32), default="priority")
    preferred_tier: Mapped[str] = mapped_column(String(32), default="balanced")
    session_affinity_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_cost_per_request: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    candidates: Mapped[list["UnifiedModelCandidate"]] = relationship(back_populates="unified_model", cascade="all, delete-orphan")


class UnifiedModelCandidate(Base, TimestampMixin):
    __tablename__ = "unified_model_candidates"
    __table_args__ = (UniqueConstraint("unified_model_id", "upstream_model_id", name="uq_unified_upstream"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unified_model_id: Mapped[int] = mapped_column(ForeignKey("unified_models.id"), index=True)
    upstream_model_id: Mapped[int] = mapped_column(ForeignKey("upstream_models.id"), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    weight: Mapped[int] = mapped_column(Integer, default=100)
    capability_overrides_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    unified_model: Mapped[UnifiedModel] = relationship(back_populates="candidates")


class AuxiliarySettings(Base):
    __tablename__ = "auxiliary_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    mode: Mapped[str] = mapped_column(String(32), default="global_pool")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuxiliaryModel(Base, TimestampMixin):
    __tablename__ = "auxiliary_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upstream_model_id: Mapped[int] = mapped_column(ForeignKey("upstream_models.id"), index=True)
    unified_model_id: Mapped[int | None] = mapped_column(ForeignKey("unified_models.id"), nullable=True, index=True)
    capabilities_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AuxiliaryWorkflow(Base, TimestampMixin):
    __tablename__ = "auxiliary_workflows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), default="global")
    unified_model_id: Mapped[int | None] = mapped_column(ForeignKey("unified_models.id"), nullable=True, index=True)
    workflow_type: Mapped[str] = mapped_column(String(64))
    input_capability: Mapped[str] = mapped_column(String(64))
    output_capability: Mapped[str] = mapped_column(String(64))
    ordered_steps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    priority: Mapped[int] = mapped_column(Integer,default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ApiToken(Base, TimestampMixin):
    __tablename__ = "api_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    token_prefix: Mapped[str] = mapped_column(String(32), index=True)
    token_hash: Mapped[str] = mapped_column(String(256), unique=True)
    scopes_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    budget_id: Mapped[int | None] = mapped_column(ForeignKey("budgets.id"), nullable=True)


class ApiTokenUnifiedModel(Base):
    """Explicit allow-list binding between a client token and unified models."""

    __tablename__ = "api_token_unified_models"
    __table_args__ = (
        UniqueConstraint("api_token_id", "unified_model_id", name="uq_api_token_unified_model"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_token_id: Mapped[int] = mapped_column(ForeignKey("api_tokens.id", ondelete="CASCADE"), index=True)
    unified_model_id: Mapped[int] = mapped_column(ForeignKey("unified_models.id", ondelete="CASCADE"), index=True)


class RequestLog(Base):
    __tablename__ = "request_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    inbound_protocol: Mapped[str] = mapped_column(String(64))
    unified_model: Mapped[str] = mapped_column(String(128))
    provider_instance_id: Mapped[int | None] = mapped_column(ForeignKey("provider_instances.id"), nullable=True)
    upstream_model_id: Mapped[int | None] = mapped_column(ForeignKey("upstream_models.id"), nullable=True)
    combo_strategy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    candidate_summary_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    auxiliary_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_token_id: Mapped[int | None] = mapped_column(ForeignKey("api_tokens.id"), nullable=True)
    api_token_prefix_snapshot: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_token_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProviderHealth(Base):
    __tablename__ = "provider_health"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upstream_model_id: Mapped[int] = mapped_column(ForeignKey("upstream_models.id"), unique=True, index=True)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class CircuitBreaker(Base):
    __tablename__ = "circuit_breakers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upstream_model_id: Mapped[int] = mapped_column(ForeignKey("upstream_models.id"), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(32), default="closed")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    half_open_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    failure_threshold: Mapped[int] = mapped_column(Integer, default=3)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=60)


class UsageHistory(Base):
    __tablename__ = "usage_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), index=True)
    api_token_id: Mapped[int | None] = mapped_column(ForeignKey("api_tokens.id"), nullable=True)
    provider_instance_id: Mapped[int | None] = mapped_column(ForeignKey("provider_instances.id"), nullable=True)
    upstream_model_id: Mapped[int | None] = mapped_column(ForeignKey("upstream_models.id"), nullable=True)
    unified_model: Mapped[str] = mapped_column(String(128))
    inbound_protocol: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuotaSnapshot(Base):
    __tablename__ = "quota_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upstream_model_id: Mapped[int] = mapped_column(ForeignKey("upstream_models.id"), index=True)
    remaining_requests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_credit: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Budget(Base, TimestampMixin):
    __tablename__ = "budgets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    scope: Mapped[str] = mapped_column(String(32))
    scope_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    billing_mode: Mapped[str] = mapped_column(String(32), default="token_cost")
    period_type: Mapped[str] = mapped_column(String(32), default="calendar_month")
    monthly_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    request_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(16), default="USD")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    spent_amount: Mapped[float] = mapped_column(Float, default=0)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    period_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    alert_threshold_percent: Mapped[int] = mapped_column(Integer, default=80)
    enforcement_action: Mapped[str] = mapped_column(String(32), default="warn")


class StoredFile(Base, TimestampMixin):
    __tablename__ = "stored_files"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_token_id: Mapped[int | None] = mapped_column(ForeignKey("api_tokens.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(512))
    purpose: Mapped[str] = mapped_column(String(64), default="assistants")
    mime_type: Mapped[str | None] = mapped_column(String(256), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(1024), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="processed")


class BatchJob(Base, TimestampMixin):
    __tablename__ = "batch_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_token_id: Mapped[int | None] = mapped_column(ForeignKey("api_tokens.id"), nullable=True)
    input_file_id: Mapped[str] = mapped_column(ForeignKey("stored_files.id"))
    endpoint: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="validating")
    request_counts_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output_file_id: Mapped[str | None] = mapped_column(ForeignKey("stored_files.id"), nullable=True)
    error_file_id: Mapped[str | None] = mapped_column(ForeignKey("stored_files.id"), nullable=True)


class MediaJob(Base, TimestampMixin):
    __tablename__ = "media_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_token_id: Mapped[int | None] = mapped_column(ForeignKey("api_tokens.id"), nullable=True)
    media_type: Mapped[str] = mapped_column(String(32))
    unified_model: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class AgentConfig(Base, TimestampMixin):
    __tablename__ = "agent_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_type: Mapped[str] = mapped_column(String(64))
    profile_name: Mapped[str] = mapped_column(String(128), default="default")
    config_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    main_model_id: Mapped[int | None] = mapped_column(ForeignKey("unified_models.id"), nullable=True)
    opus_model_id: Mapped[int | None] = mapped_column(ForeignKey("unified_models.id"), nullable=True)
    sonnet_model_id: Mapped[int | None] = mapped_column(ForeignKey("unified_models.id"), nullable=True)
    haiku_model_id: Mapped[int | None] = mapped_column(ForeignKey("unified_models.id"), nullable=True)
    last_written_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_backup_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    encrypted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebDAVProfile(Base, TimestampMixin):
    __tablename__ = "webdav_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(1024))
    username: Mapped[str | None] = mapped_column(String(256), nullable=True)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    backup_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class WebDAVSyncLog(Base):
    __tablename__ = "webdav_sync_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("webdav_profiles.id"))
    direction: Mapped[str] = mapped_column(String(32))
    remote_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    conflict_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
