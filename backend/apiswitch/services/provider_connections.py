"""Provider account lifecycle helpers shared by bootstrap and admin APIs."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, ProviderConnection, UnifiedModelCandidate

LEGACY_CONNECTION_NAME = "legacy-default"


def get_default_connection(db: Session, provider_id: int) -> ProviderConnection | None:
    return db.scalar(
        select(ProviderConnection)
        .where(
            ProviderConnection.provider_id == provider_id,
            ProviderConnection.name == LEGACY_CONNECTION_NAME,
        )
        .order_by(ProviderConnection.id)
        .limit(1)
    )


def migrate_legacy_provider_credentials(db: Session, provider: Provider | None = None) -> int:
    """Move retired provider-level credentials to an account connection.

    Candidates are atomically rebound before the old credential is cleared, so
    all subsequent requests resolve credentials through ProviderConnection.
    """
    providers = [provider] if provider is not None else db.scalars(select(Provider)).all()
    migrated = 0
    for item in providers:
        if not item.api_key_encrypted:
            continue
        connection = get_default_connection(db, item.id)
        if connection is None:
            connection = ProviderConnection(
                provider_id=item.id,
                name=LEGACY_CONNECTION_NAME,
                auth_type="api_key",
                account_label="Migrated legacy provider key",
                credential_encrypted=item.api_key_encrypted,
                priority=100,
                enabled=True,
                metadata_json={"migrated_from_provider": True},
            )
            db.add(connection)
            db.flush()
        else:
            connection.credential_encrypted = item.api_key_encrypted

        for candidate in db.scalars(
            select(UnifiedModelCandidate).where(
                UnifiedModelCandidate.provider_id == item.id,
                UnifiedModelCandidate.provider_connection_id.is_(None),
            )
        ):
            candidate.provider_connection_id = connection.id
        item.api_key_encrypted = None
        migrated += 1
    db.flush()
    return migrated
