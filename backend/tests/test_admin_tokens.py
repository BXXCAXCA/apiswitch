def test_api_token_crud(client):
    created = client.post(
        "/api/admin/tokens",
        json={"name": "local-dev", "scopes": ["gateway:invoke"]},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["name"] == "local-dev"
    assert body["enabled"] is True
    assert body["scopes"] == ["gateway:invoke"]
    assert body["token"].startswith("ask_")
    assert body["token_prefix"] == body["token"][:12]

    listed = client.get("/api/admin/tokens")
    assert listed.status_code == 200
    token_item = listed.json()[0]
    assert token_item["token_prefix"] == body["token_prefix"]
    assert "token" not in token_item

    updated = client.patch(f"/api/admin/tokens/{body['id']}", json={"enabled": False, "scopes": ["gateway:read"]})
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["scopes"] == ["gateway:read"]

    deleted = client.delete(f"/api/admin/tokens/{body['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
