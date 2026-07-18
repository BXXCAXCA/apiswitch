from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4


def _create(client, **overrides):
    payload = {"name": "token-test", "scopes": ["gateway:invoke"]}
    payload.update(overrides)
    response = client.post("/api/admin/tokens", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_token_plaintext_is_returned_once_and_crud_never_exposes_hash(client):
    created = _create(client)
    assert created["token"].startswith("ask_")
    listed = client.get("/api/admin/tokens")
    assert listed.status_code == 200
    item = next(row for row in listed.json() if row["id"] == created["id"])
    assert "token" not in item and "token_hash" not in item
    assert item["prefix"] == created["prefix"]

    rotated=client.post(f"/api/admin/tokens/{created['id']}/rotate")
    assert rotated.status_code==200
    assert rotated.json()["token"].startswith("ask_") and rotated.json()["token"]!=created["token"]
    assert client.get("/v1/models",headers={"Authorization":f"Bearer {created['token']}"}).status_code==401
    assert client.get("/v1/models",headers={"Authorization":f"Bearer {rotated.json()['token']}"}).status_code==200
    item=next(row for row in client.get("/api/admin/tokens").json() if row["id"]==created["id"])
    assert item["prefix"]==rotated.json()["prefix"] and "token" not in item

    updated = client.patch(
        f"/api/admin/tokens/{created['id']}",
        json={"scopes": ["gateway:invoke", "admin:access"], "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["scopes"] == ["gateway:invoke", "admin:access"]
    assert client.delete(f"/api/admin/tokens/{created['id']}").json() == {"deleted": True}


def test_token_expiry_timezone_scope_and_enabled_state_are_enforced(client):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    active = _create(client, expires_at=future)
    headers = {"Authorization": f"Bearer {active['token']}"}
    # A missing file reaches the protected handler (404) only after auth succeeds.
    assert client.get("/v1/files/missing", headers=headers).status_code == 404
    listed = next(row for row in client.get("/api/admin/tokens").json() if row["id"] == active["id"])
    assert listed["last_used_at"] is not None

    expired = _create(client, expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    response = client.get("/v1/files/missing", headers={"Authorization": f"Bearer {expired['token']}"})
    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "api_token_expired"

    scoped = _create(client, scopes=["admin:access"])
    response = client.get("/v1/files/missing", headers={"Authorization": f"Bearer {scoped['token']}"})
    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "insufficient_scope"

    disabled = _create(client, enabled=False)
    response = client.get("/v1/files/missing", headers={"Authorization": f"Bearer {disabled['token']}"})
    assert response.status_code == 403
    assert response.json()["detail"]["type"] == "api_token_disabled"


def test_token_validation_rejects_invalid_expiry_scopes_and_sensitive_fields(client):
    assert client.post("/api/admin/tokens", json={"expires_at": "not-a-time"}).status_code == 422
    assert client.post("/api/admin/tokens", json={"scopes": []}).status_code == 422
    created = _create(client)
    response = client.patch(f"/api/admin/tokens/{created['id']}", json={"token_hash": "forbidden"})
    assert response.status_code == 422
    assert response.json()["detail"]["stage"] == "token_validation"


def test_gateway_token_can_list_only_callable_unified_models(client):
    provider=client.post("/api/admin/provider-instances",json={"name":f"models-{uuid4().hex}","template_key":"openai","base_url":"mock://models"}).json()
    upstream=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models",json={"model_id":"catalog-upstream","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    visible=client.post("/api/admin/unified-models",json={"name":f"client-visible-{uuid4().hex}","enabled":True}).json()
    hidden=client.post("/api/admin/unified-models",json={"name":f"client-hidden-{uuid4().hex}","enabled":False}).json()
    forbidden=client.post("/api/admin/unified-models",json={"name":f"client-forbidden-{uuid4().hex}","enabled":True}).json()
    gemini_only=client.post("/api/admin/unified-models",json={"name":f"client-gemini-{uuid4().hex}","enabled":True,"enabled_protocols":["gemini_v1beta"]}).json()
    for model in (visible,hidden,forbidden,gemini_only):
        assert client.post(f"/api/admin/unified-models/{model['id']}/candidates",json={"upstream_model_id":upstream["id"]}).status_code==201

    assert client.get("/v1/models").status_code==401
    token=_create(client,name=f"models-token-{uuid4().hex}",unified_model_ids=[visible["id"],hidden["id"],gemini_only["id"]])
    response=client.get("/v1/models",headers={"Authorization":f"Bearer {token['token']}"})
    assert response.status_code==200
    assert response.json()["object"]=="list"
    by_id={item["id"]:item for item in response.json()["data"]}
    assert visible["name"] in by_id
    assert hidden["name"] not in by_id
    assert forbidden["name"] not in by_id
    assert gemini_only["name"] not in by_id
    assert by_id[visible["name"]]["object"]=="model"
    assert by_id[visible["name"]]["owned_by"]=="apiswitch"
    listed=next(item for item in client.get("/api/admin/tokens").json() if item["id"]==token["id"])
    assert set(listed["unified_model_ids"])=={hidden["id"],visible["id"],gemini_only["id"]}
    assert {item["name"] for item in listed["unified_models"]}=={visible["name"],hidden["name"],gemini_only["name"]}
    gemini_catalog=client.get("/v1beta/models",headers={"Authorization":f"Bearer {token['token']}"}).json()
    # New unified models enable the four primary ingress protocols by default.
    assert {item["baseModelId"] for item in gemini_catalog["models"]}=={visible["name"],gemini_only["name"]}
    headers={"Authorization":f"Bearer {token['token']}"}
    allowed_call=client.post("/v1/chat/completions",headers=headers,json={"model":visible["name"],"messages":[{"role":"user","content":"hello"}]})
    assert allowed_call.status_code==200,allowed_call.text
    matching_log=next(row for row in client.get("/api/admin/logs").json() if row["unified_model"]==visible["name"])
    assert matching_log["api_token_name"]==next(row["name"] for row in client.get("/api/admin/tokens").json() if row["id"]==token["id"])
    denied_call=client.post("/v1/chat/completions",headers=headers,json={"model":forbidden["name"],"messages":[{"role":"user","content":"hello"}]})
    assert denied_call.status_code==403
    assert denied_call.json()["error"]["type"]=="model_not_allowed"
    assert denied_call.json()["error"]["stage"]=="token_authorization"


def test_token_without_unified_models_has_empty_catalog_and_cannot_invoke(client):
    token=_create(client,name=f"empty-model-token-{uuid4().hex}")
    headers={"Authorization":f"Bearer {token['token']}"}
    assert client.get("/v1/models",headers=headers).json()["data"]==[]
    response=client.post("/v1/chat/completions",headers=headers,json={"model":"anything","messages":[{"role":"user","content":"hello"}]})
    assert response.status_code==404
    assert response.json()["error"]["type"]=="model_not_found"
    assert response.json()["error"]["stage"]=="model_resolution"
    assert response.json()["error"]["details"]["allowed_models"]==[]
