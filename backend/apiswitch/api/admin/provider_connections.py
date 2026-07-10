from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import Provider, ProviderConnection, ProviderNode
from apiswitch.schemas.provider_connections import (
    ProviderConnectionCreate,
    ProviderConnectionRead,
    ProviderConnectionUpdate,
    ProviderNodeCreate,
    ProviderNodeRead,
    ProviderNodeUpdate,
)
from apiswitch.security.crypto import secret_crypto

router = APIRouter(prefix="/api/admin/providers", tags=["Admin - Provider Connections"])


def _get_provider(db: Session, provider_id: int) -> Provider:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return provider


def _get_connection(db: Session, provider_id: int, connection_id: int) -> ProviderConnection:
    connection = db.get(ProviderConnection, connection_id)
    if connection is None or connection.provider_id != provider_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider connection not found")
    return connection


def _get_node(db: Session, provider_id: int, node_id: int) -> ProviderNode:
    node = db.get(ProviderNode, node_id)
    if node is None or node.provider_id != provider_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider node not found")
    return node


def _encrypt(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return secret_crypto.encrypt(value)


def _connection_read(connection: ProviderConnection) -> ProviderConnectionRead:
    return ProviderConnectionRead(
        id=connection.id,
        provider_id=connection.provider_id,
        name=connection.name,
        auth_type=connection.auth_type,
        account_label=connection.account_label,
        credential_configured=bool(connection.credential_encrypted),
        refresh_token_configured=bool(connection.refresh_token_encrypted),
        expires_at=connection.expires_at,
        priority=connection.priority,
        enabled=connection.enabled,
        metadata=connection.metadata_json or {},
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


def _node_read(node: ProviderNode) -> ProviderNodeRead:
    data = node.capabilities_json or {}
    return ProviderNodeRead(
        id=node.id,
        provider_id=node.provider_id,
        connection_id=node.connection_id,
        name=node.name,
        base_url=node.base_url,
        region=node.region,
        enabled=node.enabled,
        weight=node.weight,
        capabilities=data.get("capabilities", []),
        metadata=node.metadata_json or {},
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def _validate_connection_for_provider(db: Session, provider_id: int, connection_id: int | None) -> None:
    if connection_id is not None:
        _get_connection(db, provider_id, connection_id)


@router.get("/{provider_id}/connections")
async def list_provider_connections(
    provider_id: int,
    db: Session = Depends(get_db),
) -> list[ProviderConnectionRead]:
    _get_provider(db, provider_id)
    connections = db.scalars(
        select(ProviderConnection)
        .where(ProviderConnection.provider_id == provider_id)
        .order_by(ProviderConnection.priority.desc(), ProviderConnection.id)
    ).all()
    return [_connection_read(connection) for connection in connections]


@router.post("/{provider_id}/connections")
async def create_provider_connection(
    provider_id: int,
    payload: ProviderConnectionCreate,
    db: Session = Depends(get_db),
) -> ProviderConnectionRead:
    _get_provider(db, provider_id)
    connection = ProviderConnection(
        provider_id=provider_id,
        name=payload.name,
        auth_type=payload.auth_type,
        account_label=payload.account_label,
        credential_encrypted=_encrypt(payload.credential),
        refresh_token_encrypted=_encrypt(payload.refresh_token),
        expires_at=payload.expires_at,
        priority=payload.priority,
        enabled=payload.enabled,
        metadata_json=payload.metadata,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _connection_read(connection)


@router.patch("/{provider_id}/connections/{connection_id}")
async def update_provider_connection(
    provider_id: int,
    connection_id: int,
    payload: ProviderConnectionUpdate,
    db: Session = Depends(get_db),
) -> ProviderConnectionRead:
    connection = _get_connection(db, provider_id, connection_id)
    data = payload.model_dump(exclude_unset=True)
    if "credential" in data:
        connection.credential_encrypted = _encrypt(data.pop("credential"))
    if "refresh_token" in data:
        connection.refresh_token_encrypted = _encrypt(data.pop("refresh_token"))
    if "metadata" in data:
        connection.metadata_json = data.pop("metadata")
    for key, value in data.items():
        setattr(connection, key, value)
    db.commit()
    db.refresh(connection)
    return _connection_read(connection)


@router.delete("/{provider_id}/connections/{connection_id}")
async def delete_provider_connection(
    provider_id: int,
    connection_id: int,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    connection = _get_connection(db, provider_id, connection_id)
    linked_node = db.scalar(select(ProviderNode).where(ProviderNode.connection_id == connection_id).limit(1))
    if linked_node is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provider connection is still used by a provider node",
        )
    db.delete(connection)
    db.commit()
    return {"deleted": True}


@router.get("/{provider_id}/nodes")
async def list_provider_nodes(
    provider_id: int,
    connection_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ProviderNodeRead]:
    _get_provider(db, provider_id)
    statement = select(ProviderNode).where(ProviderNode.provider_id == provider_id)
    if connection_id is not None:
        _validate_connection_for_provider(db, provider_id, connection_id)
        statement = statement.where(ProviderNode.connection_id == connection_id)
    nodes = db.scalars(statement.order_by(ProviderNode.weight.desc(), ProviderNode.id)).all()
    return [_node_read(node) for node in nodes]


@router.post("/{provider_id}/nodes")
async def create_provider_node(
    provider_id: int,
    payload: ProviderNodeCreate,
    db: Session = Depends(get_db),
) -> ProviderNodeRead:
    _get_provider(db, provider_id)
    _validate_connection_for_provider(db, provider_id, payload.connection_id)
    node = ProviderNode(
        provider_id=provider_id,
        connection_id=payload.connection_id,
        name=payload.name,
        base_url=payload.base_url,
        region=payload.region,
        enabled=payload.enabled,
        weight=payload.weight,
        capabilities_json={"capabilities": payload.capabilities},
        metadata_json=payload.metadata,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return _node_read(node)


@router.patch("/{provider_id}/nodes/{node_id}")
async def update_provider_node(
    provider_id: int,
    node_id: int,
    payload: ProviderNodeUpdate,
    db: Session = Depends(get_db),
) -> ProviderNodeRead:
    node = _get_node(db, provider_id, node_id)
    data = payload.model_dump(exclude_unset=True)
    if "connection_id" in data:
        _validate_connection_for_provider(db, provider_id, data["connection_id"])
    if "capabilities" in data:
        node.capabilities_json = {"capabilities": data.pop("capabilities")}
    if "metadata" in data:
        node.metadata_json = data.pop("metadata")
    for key, value in data.items():
        setattr(node, key, value)
    db.commit()
    db.refresh(node)
    return _node_read(node)


@router.delete("/{provider_id}/nodes/{node_id}")
async def delete_provider_node(
    provider_id: int,
    node_id: int,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    node = _get_node(db, provider_id, node_id)
    db.delete(node)
    db.commit()
    return {"deleted": True}
