"""Controlled, Connection-level quota refreshes for providers with an official endpoint."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, ProviderConnection, QuotaSnapshot
from apiswitch.db.session import SessionLocal
from apiswitch.providers.quota import quota_from_headers
from apiswitch.security.crypto import SecretCryptoError, secret_crypto


class QuotaRefreshError(ValueError):
    """A safe, operator-actionable quota refresh failure."""


logger = logging.getLogger(__name__)


def _relative_refresh_url(base_url: str, path: object) -> str:
    if not isinstance(path, str) or not path.startswith("/"):
        raise QuotaRefreshError(
            "Connection metadata must set quota_refresh_path to an absolute relative path"
        )
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or any(part == ".." for part in parsed.path.split("/")):
        raise QuotaRefreshError(
            "quota_refresh_path must stay below the configured provider base URL"
        )
    return f"{base_url.rstrip('/')}{path}"


def _request_headers(provider: Provider, connection: ProviderConnection) -> dict[str, str]:
    metadata = connection.metadata_json or {}
    style = str(metadata.get("quota_refresh_auth", "auto"))
    allowed = {"auto", "none", "bearer", "x-api-key", "x-goog-api-key"}
    if style not in allowed:
        raise QuotaRefreshError(
            "quota_refresh_auth must be auto, none, bearer, x-api-key, or x-goog-api-key"
        )
    if style == "none":
        return {}
    if not connection.credential_encrypted:
        raise QuotaRefreshError("Provider connection has no credential for quota refresh")
    try:
        credential = secret_crypto.decrypt(connection.credential_encrypted)
    except SecretCryptoError as exc:
        raise QuotaRefreshError(str(exc)) from exc
    if not credential:
        raise QuotaRefreshError("Provider connection has no credential for quota refresh")
    if style == "auto":
        if provider.type == "anthropic":
            style = "x-api-key"
        elif provider.type == "gemini" and connection.auth_type != "oauth":
            style = "x-goog-api-key"
        else:
            style = "bearer"
    if style == "bearer":
        return {"Authorization": f"Bearer {credential}"}
    if style == "x-api-key":
        return {"x-api-key": credential}
    return {"x-goog-api-key": credential}


def _json_value(payload: object, path: object) -> object | None:
    if not isinstance(path, str) or not path:
        return None
    value: object = payload
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _number(value: object, *, integer: bool = False) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if integer else number


def _reset_at(value: object) -> datetime | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=UTC).replace(tzinfo=None)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


async def refresh_connection_quota(
    db: Session,
    *,
    provider: Provider,
    connection: ProviderConnection,
    client: httpx.AsyncClient | None = None,
) -> QuotaSnapshot:
    """Call an opt-in provider quota endpoint and persist a normalized snapshot.

    ``quota_refresh_path`` is deliberately relative to ``Provider.base_url`` so
    an administrator cannot turn this gateway endpoint into an arbitrary SSRF
    primitive. Optional ``quota_refresh_fields`` maps canonical fields to JSON
    dot paths when an upstream returns quota values in its JSON body.
    """
    metadata = connection.metadata_json or {}
    url = _relative_refresh_url(provider.base_url, metadata.get("quota_refresh_path"))
    method = str(metadata.get("quota_refresh_method", "GET")).upper()
    if method != "GET":
        raise QuotaRefreshError("Only GET quota refresh endpoints are supported")
    headers = _request_headers(provider, connection)

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=provider.timeout_seconds)
    try:
        response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise QuotaRefreshError(f"Quota refresh request failed: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()
    if response.status_code >= 400:
        raise QuotaRefreshError(f"Quota refresh endpoint returned HTTP {response.status_code}")

    quota = quota_from_headers(dict(response.headers)) or {
        "remaining_requests": None,
        "remaining_tokens": None,
        "remaining_credit": None,
        "reset_at": None,
        "raw": {},
    }
    fields = metadata.get("quota_refresh_fields", {})
    if fields and not isinstance(fields, dict):
        raise QuotaRefreshError(
            "quota_refresh_fields must be an object mapping fields to JSON paths"
        )
    payload: object = {}
    if isinstance(fields, dict) and fields:
        try:
            payload = response.json()
        except ValueError as exc:
            raise QuotaRefreshError(
                "Quota refresh response is not JSON as required by quota_refresh_fields"
            ) from exc
        requests = _number(_json_value(payload, fields.get("remaining_requests")), integer=True)
        tokens = _number(_json_value(payload, fields.get("remaining_tokens")), integer=True)
        credit = _number(_json_value(payload, fields.get("remaining_credit")))
        reset = _reset_at(_json_value(payload, fields.get("reset_at")))
        if requests is not None:
            quota["remaining_requests"] = requests
        if tokens is not None:
            quota["remaining_tokens"] = tokens
        if credit is not None:
            quota["remaining_credit"] = credit
        if reset is not None:
            quota["reset_at"] = reset

    raw = dict(quota["raw"])
    raw.update({"source": "provider_quota_refresh", "path": metadata["quota_refresh_path"]})
    snapshot = QuotaSnapshot(
        provider_connection_id=connection.id,
        remaining_requests=quota["remaining_requests"],
        remaining_tokens=quota["remaining_tokens"],
        remaining_credit=quota["remaining_credit"],
        reset_at=quota["reset_at"],
        raw_json=raw,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def _configured_interval_minutes(connection: ProviderConnection) -> int | None:
    metadata = connection.metadata_json or {}
    if metadata.get("quota_refresh_enabled") is not True or not metadata.get("quota_refresh_path"):
        return None
    raw = metadata.get("quota_refresh_interval_minutes", 15)
    if isinstance(raw, bool):
        return None
    try:
        interval = int(raw)
    except (TypeError, ValueError):
        return None
    return interval if 1 <= interval <= 1440 else None


async def refresh_due_connection_quotas(now: datetime | None = None) -> int:
    """Refresh explicitly enabled Connection quotas once and return the success count."""
    now = now or datetime.utcnow()
    with SessionLocal() as db:
        connection_ids = db.scalars(
            select(ProviderConnection.id).where(ProviderConnection.enabled.is_(True))
        ).all()

    refreshed = 0
    for connection_id in connection_ids:
        with SessionLocal() as db:
            connection = db.get(ProviderConnection, connection_id)
            if connection is None:
                continue
            interval = _configured_interval_minutes(connection)
            if interval is None:
                continue
            last_captured = db.scalar(
                select(QuotaSnapshot.captured_at)
                .where(QuotaSnapshot.provider_connection_id == connection.id)
                .order_by(QuotaSnapshot.captured_at.desc())
                .limit(1)
            )
            if last_captured is not None and (now - last_captured).total_seconds() < interval * 60:
                continue
            provider = db.get(Provider, connection.provider_id)
            if provider is None:
                continue
            try:
                await refresh_connection_quota(db, provider=provider, connection=connection)
                refreshed += 1
            except QuotaRefreshError as exc:
                logger.warning("Quota refresh for connection %s failed: %s", connection.id, exc)
    return refreshed


async def run_configured_quota_refresh_loop() -> None:
    """Run the local quota scheduler until the FastAPI lifespan cancels it."""
    while True:
        await refresh_due_connection_quotas()
        await asyncio.sleep(60)
