"""Controlled migration of credentials written by the retired stage-1 cipher."""

from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, ProviderConnection, RequestLog, WebDAVProfile
from apiswitch.security.crypto import secret_crypto


def _migrate_value(value: str | None) -> tuple[str | None, bool]:
    if not secret_crypto.needs_migration(value):
        return value, False
    return secret_crypto.encrypt(secret_crypto.decrypt(value or "")), True


def migrate_legacy_secrets(db: Session) -> dict[str, int]:
    """Re-encrypt all legacy credential values in one explicit transaction."""
    migrated = {
        "provider_api_keys": 0,
        "connection_credentials": 0,
        "refresh_tokens": 0,
        "webdav_passwords": 0,
        "debug_request_bodies": 0,
        "debug_response_bodies": 0,
    }

    for provider in db.query(Provider).all():
        provider.api_key_encrypted, changed = _migrate_value(provider.api_key_encrypted)
        migrated["provider_api_keys"] += int(changed)

    for connection in db.query(ProviderConnection).all():
        connection.credential_encrypted, changed = _migrate_value(connection.credential_encrypted)
        migrated["connection_credentials"] += int(changed)
        connection.refresh_token_encrypted, changed = _migrate_value(connection.refresh_token_encrypted)
        migrated["refresh_tokens"] += int(changed)

    for profile in db.query(WebDAVProfile).all():
        profile.password_encrypted, changed = _migrate_value(profile.password_encrypted)
        migrated["webdav_passwords"] += int(changed)

    for request_log in db.query(RequestLog).all():
        request_log.debug_request_body_encrypted, changed = _migrate_value(
            request_log.debug_request_body_encrypted
        )
        migrated["debug_request_bodies"] += int(changed)
        request_log.debug_response_body_encrypted, changed = _migrate_value(
            request_log.debug_response_body_encrypted
        )
        migrated["debug_response_bodies"] += int(changed)

    db.commit()
    return migrated
