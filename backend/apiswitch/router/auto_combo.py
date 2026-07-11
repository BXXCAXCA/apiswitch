"""Dynamic candidate discovery for Unified Models in ``auto`` routing mode."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, ProviderConnection, ProviderModel, ProviderNode, UnifiedModel, UnifiedModelCandidate


def _capabilities(value: dict | None) -> set[str]:
    raw = (value or {}).get("capabilities", [])
    return {str(item) for item in raw} if isinstance(raw, list) else set()


def _routing_mode(model: UnifiedModel) -> str:
    routing = (model.capabilities_json or {}).get("routing", {})
    return routing.get("routing_mode", "static") if isinstance(routing, dict) else "static"


def _available_targets(db: Session, provider: Provider) -> list[tuple[ProviderConnection | None, ProviderNode | None]]:
    """Return every enabled account/endpoint combination, retaining legacy providers."""
    connections = db.scalars(
        select(ProviderConnection).where(
            ProviderConnection.provider_id == provider.id,
            ProviderConnection.enabled.is_(True),
        )
    ).all()
    active_connections = [
        connection
        for connection in connections
        if connection.expires_at is None or connection.expires_at > datetime.utcnow()
    ]
    if not active_connections:
        return [(None, None)] if not connections else []

    targets: list[tuple[ProviderConnection | None, ProviderNode | None]] = []
    for connection in active_connections:
        nodes = db.scalars(
            select(ProviderNode).where(
                ProviderNode.provider_id == provider.id,
                ProviderNode.connection_id == connection.id,
                ProviderNode.enabled.is_(True),
            )
        ).all()
        if nodes:
            targets.extend((connection, node) for node in nodes)
        else:
            targets.append((connection, None))
    return targets


def materialize_auto_candidates(db: Session, unified_model: UnifiedModel) -> int:
    """Persist the current auto pool so circuit breakers and health are durable.

    A candidate is only created once for a model/provider/model/account/node tuple;
    it becomes a normal routed candidate thereafter and keeps its health history.
    """
    if _routing_mode(unified_model) != "auto":
        return 0
    required = _capabilities(unified_model.capabilities_json)
    rows = db.execute(
        select(Provider, ProviderModel)
        .join(ProviderModel, ProviderModel.provider_id == Provider.id)
        .where(Provider.enabled.is_(True), ProviderModel.enabled.is_(True))
    ).all()
    created = 0
    for provider, provider_model in rows:
        capabilities = _capabilities(provider_model.capabilities_json)
        if required and not required.issubset(capabilities):
            continue
        for connection, node in _available_targets(db, provider):
            exists = db.scalar(
                select(UnifiedModelCandidate.id).where(
                    UnifiedModelCandidate.unified_model_id == unified_model.id,
                    UnifiedModelCandidate.provider_id == provider.id,
                    UnifiedModelCandidate.provider_connection_id == (connection.id if connection else None),
                    UnifiedModelCandidate.provider_node_id == (node.id if node else None),
                    UnifiedModelCandidate.upstream_model == provider_model.model_name,
                ).limit(1)
            )
            if exists is not None:
                continue
            priority = 100
            if connection is not None:
                priority += connection.priority
            if node is not None:
                priority += node.weight
            db.add(
                UnifiedModelCandidate(
                    unified_model_id=unified_model.id,
                    provider_id=provider.id,
                    provider_connection_id=connection.id if connection else None,
                    provider_node_id=node.id if node else None,
                    upstream_model=provider_model.model_name,
                    manual_priority=priority,
                    enabled=True,
                    capabilities_json={"capabilities": sorted(capabilities), "auto_managed": True},
                )
            )
            created += 1
    if created:
        db.flush()
    return created
