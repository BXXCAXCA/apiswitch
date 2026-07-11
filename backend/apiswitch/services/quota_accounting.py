from sqlalchemy.orm import Session

from apiswitch.db.models import QuotaSnapshot
from apiswitch.providers.quota import quota_from_headers


def record_adapter_quota_snapshot(db: Session, *, provider: object, provider_connection_id: int | None) -> None:
    if provider_connection_id is None:
        return
    quota = quota_from_headers(getattr(provider, "last_response_headers", None))
    if quota is None:
        return
    db.add(
        QuotaSnapshot(
            provider_connection_id=provider_connection_id,
            remaining_requests=quota["remaining_requests"],
            remaining_tokens=quota["remaining_tokens"],
            remaining_credit=quota["remaining_credit"],
            reset_at=quota["reset_at"],
            raw_json=quota["raw"],
        )
    )
