def test_provider_connection_and_node_crud(client):
    provider = client.get("/api/admin/providers").json()[0]
    provider_id = provider["id"]

    created_connection = client.post(
        f"/api/admin/providers/{provider_id}/connections",
        json={
            "name": "secondary-account",
            "auth_type": "oauth",
            "account_label": "team",
            "credential": "access-secret",
            "refresh_token": "refresh-secret",
            "priority": 80,
            "enabled": True,
            "metadata": {"free_tier": True},
        },
    )
    assert created_connection.status_code == 200
    connection = created_connection.json()
    assert connection["credential_configured"] is True
    assert connection["refresh_token_configured"] is True
    assert "access-secret" not in str(connection)
    assert "refresh-secret" not in str(connection)

    listed_connections = client.get(f"/api/admin/providers/{provider_id}/connections")
    assert listed_connections.status_code == 200
    assert any(item["name"] == "secondary-account" for item in listed_connections.json())

    created_node = client.post(
        f"/api/admin/providers/{provider_id}/nodes",
        json={
            "name": "singapore-node",
            "base_url": "https://example.invalid/v1",
            "connection_id": connection["id"],
            "region": "ap-southeast-1",
            "enabled": True,
            "weight": 120,
            "capabilities": ["chat", "embeddings"],
            "metadata": {"proxy": False},
        },
    )
    assert created_node.status_code == 200
    node = created_node.json()
    assert node["connection_id"] == connection["id"]
    assert node["capabilities"] == ["chat", "embeddings"]

    filtered_nodes = client.get(
        f"/api/admin/providers/{provider_id}/nodes",
        params={"connection_id": connection["id"]},
    )
    assert filtered_nodes.status_code == 200
    assert len(filtered_nodes.json()) == 1

    blocked_delete = client.delete(
        f"/api/admin/providers/{provider_id}/connections/{connection['id']}"
    )
    assert blocked_delete.status_code == 409

    updated_connection = client.patch(
        f"/api/admin/providers/{provider_id}/connections/{connection['id']}",
        json={"credential": None, "enabled": False},
    )
    assert updated_connection.status_code == 200
    assert updated_connection.json()["credential_configured"] is False
    assert updated_connection.json()["enabled"] is False

    deleted_node = client.delete(f"/api/admin/providers/{provider_id}/nodes/{node['id']}")
    assert deleted_node.status_code == 200

    deleted_connection = client.delete(
        f"/api/admin/providers/{provider_id}/connections/{connection['id']}"
    )
    assert deleted_connection.status_code == 200
