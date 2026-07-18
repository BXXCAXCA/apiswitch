from __future__ import annotations

from uuid import uuid4
from datetime import datetime

from fastapi.testclient import TestClient

from apiswitch.db.models import Budget
from apiswitch.services.budget_enforcement import refresh_budget_period


def _route(client:TestClient):
    provider=client.post("/api/admin/provider-instances",json={"name":f"budget-{uuid4().hex}","template_key":"openai","base_url":"mock://budget"}).json()
    upstream=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models",json={"model_id":"budget-model","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"budget-route-{uuid4().hex}","enabled_protocols":["openai_chat"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":upstream["id"]})
    token=client.post("/api/admin/tokens",json={"name":"budget-client","unified_model_ids":[unified["id"]]}).json()["token"]
    return unified,{"Authorization":f"Bearer {token}"}


def test_exhausted_reject_budget_stops_request_before_upstream(client:TestClient):
    unified,headers=_route(client)
    budget=client.post("/api/admin/budgets",json={"name":"blocked","scope":"global","monthly_limit":0,"enforcement_action":"reject"})
    assert budget.status_code==201

    response=client.post("/v1/chat/completions",headers=headers,json={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]})

    assert response.status_code==400
    assert response.json()["error"]["type"]=="budget_exceeded"
    log=client.get("/api/admin/logs").json()[0]
    assert log["failure_stage"]=="budget_check" and log["provider_instance_id"] is None


def _priced_route(client:TestClient):
    provider=client.post("/api/admin/provider-instances",json={"name":f"priced-{uuid4().hex}","template_key":"openai","base_url":"mock://priced"}).json()
    models=[]
    for model_id,price in (("expensive",5),("free",0),("cheap",1)):
        models.append(client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models",json={"model_id":model_id,"input_capabilities_json":["text"],"output_capabilities_json":["text"],"input_price":price,"output_price":price}).json())
    unified=client.post("/api/admin/unified-models",json={"name":f"priced-route-{uuid4().hex}","enabled_protocols":["openai_chat"]}).json()
    for priority,model in enumerate(models,start=1):client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":model["id"],"priority":priority})
    token=client.post("/api/admin/tokens",json={"name":"priced-client","unified_model_ids":[unified["id"]]}).json()["token"]
    return unified,models,{"Authorization":f"Bearer {token}"}


def test_exhausted_budget_can_fallback_to_free_or_cheapest_eligible_candidate(client:TestClient):
    unified,models,headers=_priced_route(client)
    payload={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]}
    free_budget=client.post("/api/admin/budgets",json={"name":"free-only","scope":"global","monthly_limit":0,"enforcement_action":"fallback_to_free"}).json()
    assert client.post("/v1/chat/completions",headers=headers,json=payload).status_code==200
    assert client.get("/api/admin/logs").json()[0]["upstream_model_id"]==models[1]["id"]

    client.delete(f"/api/admin/budgets/{free_budget['id']}")
    client.post("/api/admin/budgets",json={"name":"cheapest","scope":"global","monthly_limit":0,"enforcement_action":"fallback_to_cheapest"})
    # The free candidate is still the mathematically cheapest candidate.
    assert client.post("/v1/chat/completions",headers=headers,json=payload).status_code==200
    assert client.get("/api/admin/logs").json()[0]["upstream_model_id"]==models[1]["id"]


def test_free_fallback_fails_explicitly_when_no_free_candidate_exists(client:TestClient):
    unified,models,headers=_priced_route(client)
    client.patch(f"/api/admin/upstream-models/{models[1]['id']}",json={"input_price":2,"output_price":2})
    client.post("/api/admin/budgets",json={"name":"free-missing","scope":"global","monthly_limit":0,"enforcement_action":"fallback_to_free"})
    response=client.post("/v1/chat/completions",headers=headers,json={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]})
    assert response.status_code==400
    assert response.json()["error"]["type"]=="budget_exceeded"


def test_request_count_budget_can_target_one_upstream_model(client:TestClient):
    provider=client.post("/api/admin/provider-instances",json={"name":f"counted-{uuid4().hex}","template_key":"openai","base_url":"mock://counted"}).json()
    upstream=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models",json={"model_id":"counted-model","input_capabilities_json":["text"],"output_capabilities_json":["text"]}).json()
    unified=client.post("/api/admin/unified-models",json={"name":f"counted-route-{uuid4().hex}","enabled_protocols":["openai_chat"]}).json()
    client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":upstream["id"]})
    token=client.post("/api/admin/tokens",json={"name":"counted-client","unified_model_ids":[unified["id"]]}).json()["token"]
    budget=client.post("/api/admin/budgets",json={"name":"five-hour-count","scope":"upstream_model","scope_id":str(upstream["id"]),"billing_mode":"request_count","period_type":"rolling_5_hours","limit_value":2,"enforcement_action":"reject"})
    assert budget.status_code==201
    assert budget.json()["request_limit"]==2 and budget.json()["usage_value"]==0

    payload={"model":unified["name"],"messages":[{"role":"user","content":"hello"}]};headers={"Authorization":f"Bearer {token}"}
    assert client.post("/v1/chat/completions",headers=headers,json=payload).status_code==200
    assert client.post("/v1/chat/completions",headers=headers,json=payload).status_code==200
    blocked=client.post("/v1/chat/completions",headers=headers,json=payload)
    assert blocked.status_code==400 and blocked.json()["error"]["type"]=="budget_exceeded"
    saved=next(row for row in client.get("/api/admin/budgets").json() if row["id"]==budget.json()["id"])
    assert saved["request_count"]==2 and saved["usage_value"]==2
    assert saved["scope"]=="upstream_model" and saved["period_ends_at"]

    client.delete(f"/api/admin/budgets/{budget.json()['id']}")
    provider_budget=client.post("/api/admin/budgets",json={"name":"provider-daily-count","scope":"provider_instance","scope_id":str(provider["id"]),"billing_mode":"request_count","period_type":"calendar_day","limit_value":1,"enforcement_action":"reject"})
    assert provider_budget.status_code==201 and provider_budget.json()["scope"]=="provider_instance"
    assert client.post("/v1/chat/completions",headers=headers,json=payload).status_code==200
    blocked=client.post("/v1/chat/completions",headers=headers,json=payload)
    assert blocked.status_code==400 and blocked.json()["error"]["type"]=="budget_exceeded"


def test_budget_periods_reset_at_china_calendar_boundaries():
    weekly=Budget(name="weekly",scope="global",billing_mode="request_count",period_type="calendar_week",request_limit=10,request_count=7,spent_amount=0,period_started_at=datetime(2026,7,5,16))
    end=refresh_budget_period(weekly,now=datetime(2026,7,18,4))
    assert weekly.period_started_at==datetime(2026,7,12,16)
    assert end==datetime(2026,7,19,16)
    assert weekly.request_count==0

    rolling=Budget(name="rolling",scope="global",billing_mode="request_count",period_type="rolling_5_hours",request_limit=10,request_count=4,spent_amount=0,period_started_at=datetime(2026,7,18,0))
    end=refresh_budget_period(rolling,now=datetime(2026,7,18,6))
    assert rolling.period_started_at==datetime(2026,7,18,6)
    assert end==datetime(2026,7,18,11)
    assert rolling.request_count==0
