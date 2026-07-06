def test_webdav_profile_crud_and_mock_connection(client):
    created = client.post(
        "/api/admin/webdav",
        json={
            "name": "mock-sync",
            "url": "mock://webdav",
            "username": "demo",
            "password": "secret-password",
            "enabled": True,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["name"] == "mock-sync"
    assert body["password_configured"] is True
    assert "secret-password" not in str(body)

    listed = client.get("/api/admin/webdav")
    assert listed.status_code == 200
    item = listed.json()[0]
    assert item["name"] == "mock-sync"
    assert "password" not in item

    tested = client.post(f"/api/admin/webdav/{body['id']}/test")
    assert tested.status_code == 200
    assert tested.json()["ok"] is True

    updated = client.patch(
        f"/api/admin/webdav/{body['id']}",
        json={"enabled": False, "password": None},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["password_configured"] is False

    deleted = client.delete(f"/api/admin/webdav/{body['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
