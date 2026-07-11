from apiswitch.providers.quota import quota_from_headers


def test_quota_header_normalization():
    quota = quota_from_headers(
        {
            "x-ratelimit-remaining-requests": "42",
            "x-ratelimit-remaining-tokens": "12000",
            "x-ratelimit-remaining-credit": "3.5",
            "retry-after": "60",
        }
    )
    assert quota is not None
    assert quota["remaining_requests"] == 42
    assert quota["remaining_tokens"] == 12000
    assert quota["remaining_credit"] == 3.5
    assert quota["reset_at"] is not None


def test_adapter_quota_snapshot_is_persisted(client):
    from apiswitch.api.deps import get_db
    from apiswitch.services.quota_accounting import record_adapter_quota_snapshot

    provider = client.get("/api/admin/providers").json()[0]
    connection = client.post(
        f"/api/admin/providers/{provider['id']}/connections",
        json={"name": "quota-account", "auth_type": "api_key", "credential": "quota-secret"},
    ).json()

    class Adapter:
        last_response_headers = {"x-ratelimit-remaining-requests": "7"}

    db = next(get_db())
    try:
        record_adapter_quota_snapshot(db, provider=Adapter(), provider_connection_id=connection["id"])
        db.commit()
    finally:
        db.close()
    snapshots = client.get(
        "/api/admin/accounting/quota-snapshots",
        params={"provider_connection_id": connection["id"]},
    )
    assert snapshots.status_code == 200
    assert snapshots.json()[0]["remaining_requests"] == 7
