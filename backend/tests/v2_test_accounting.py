from __future__ import annotations

from uuid import uuid4


def test_pricing_usage_grouping_log_filters_and_token_deletion_snapshot(client):
    provider=client.post("/api/admin/provider-instances",json={"name":f"accounting-{uuid4().hex}","template_key":"openai","base_url":"mock://accounting"}).json()
    upstream=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models",json={"model_id":"priced","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    priced=client.patch(f"/api/admin/accounting/pricing/{upstream['id']}",json={"input_price":1.5,"output_price":2.5,"cached_input_price":0.5,"currency":"USD","pricing_source":"manual","pricing_effective_at":"2026-07-16T00:00:00Z"})
    assert priced.status_code==200
    assert priced.json()["input_price"]==1.5 and priced.json()["pricing_source"]=="manual"

    unified=client.post("/api/admin/unified-models",json={"name":f"accounting-model-{uuid4().hex}","enabled_protocols":["openai_chat"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":upstream["id"]})
    created=client.post("/api/admin/tokens",json={"name":"accounting-token","unified_model_ids":[unified["id"]]}).json()
    headers={"Authorization":f"Bearer {created['token']}"}
    assert client.post("/v1/chat/completions",headers=headers,json={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]}).status_code==200

    usage=client.get("/api/admin/accounting/usage").json()
    assert usage["requests"]==usage["successful_requests"]==1
    assert usage["by_provider_instance"][0]["key"]==provider["id"]
    assert usage["by_upstream_model"][0]["key"]==upstream["id"]
    assert usage["by_unified_model"][0]["key"]==unified["name"]
    assert usage["by_protocol"][0]["key"]=="openai_chat"
    assert usage["by_api_token"][0]["key"]==created["id"]

    assert client.get("/api/admin/logs",params={"success":False}).json()==[]
    matching=client.get("/api/admin/logs",params={"success":True,"unified_model":unified["name"],"api_token_id":created["id"]}).json()
    assert len(matching)==1 and matching[0]["api_token_prefix"]==created["prefix"]

    assert client.delete(f"/api/admin/tokens/{created['id']}").status_code==200
    retained=client.get("/api/admin/logs").json()[0]
    assert retained["api_token_id"] is None and retained["api_token_prefix"]==created["prefix"]
