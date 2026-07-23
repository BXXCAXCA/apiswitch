from datetime import timedelta
from uuid import uuid4

from apiswitch.db.models import ProviderHealth, QuotaSnapshot, UnifiedModel, UpstreamModel, UsageHistory
from apiswitch.db.base import utc_now
from apiswitch.db.session import SessionLocal
from apiswitch.protocols.canonical import CanonicalRequest
from apiswitch.protocols.canonical import ProtocolError
from apiswitch.routing import engine


def _combo_fixture(client):
    provider = client.post("/api/admin/provider-instances", json={"name": f"combo-{uuid4().hex}", "template_key": "openai", "base_url": "mock://combo"}).json()
    upstreams=[]
    for index in range(3):
        upstreams.append(client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models", json={"model_id": f"model-{index}", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"], "input_price": 3-index, "output_price": 3-index}).json())
    unified=client.post("/api/admin/unified-models",json={"name":f"combo-{uuid4().hex}","enabled_protocols":["openai_chat"],"routing_mode":"combo","combo_strategy":"priority"}).json()
    candidates=[]
    for index,upstream in enumerate(upstreams):
        candidates.append(client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":upstream["id"],"priority":index+1,"weight":(index+1)*10}).json())
    return unified,upstreams,candidates


def test_all_combo_strategies_and_session_affinity_use_generation_two_models(client,monkeypatch):
    unified_data,upstreams,candidates=_combo_fixture(client)
    request=CanonicalRequest("chat","openai_chat",unified_data["name"],messages=[{"role":"user","content":"x"}])
    with SessionLocal() as db:
        unified=db.get(UnifiedModel,unified_data["id"])
        unified.combo_strategy="priority";db.commit()
        assert engine.route_candidates(db,request)[1][0].upstream.id==upstreams[0]["id"]

        unified.combo_strategy="weighted";db.commit()
        monkeypatch.setattr(engine.random,"choices",lambda population,weights,k:[population[-1]])
        assert engine.route_candidates(db,request)[1][0].upstream.id==upstreams[2]["id"]

        unified.combo_strategy="round_robin";db.commit();engine._round_robin.pop(unified.id,None)
        first=engine.route_candidates(db,request)[1][0].upstream.id
        second=engine.route_candidates(db,request)[1][0].upstream.id
        assert (first,second)==(upstreams[0]["id"],upstreams[1]["id"])

        db.add_all([UsageHistory(request_id=f"used-{index}",upstream_model_id=upstreams[0]["id"],unified_model=unified.name,inbound_protocol="openai_chat") for index in range(2)])
        unified.combo_strategy="least_used";db.commit()
        assert engine.route_candidates(db,request)[1][0].upstream.id==upstreams[1]["id"]

        for index,item in enumerate(upstreams):
            row=db.get(UpstreamModel,item["id"]);row.input_price=3-index;row.output_price=3-index
        unified.combo_strategy="cost_optimized";db.commit()
        assert engine.route_candidates(db,request)[1][0].upstream.id==upstreams[2]["id"]

        db.add_all([QuotaSnapshot(upstream_model_id=item["id"],remaining_credit=float(index+1)) for index,item in enumerate(upstreams)])
        unified.combo_strategy="quota_headroom";db.commit()
        assert engine.route_candidates(db,request)[1][0].upstream.id==upstreams[2]["id"]

        now=utc_now();db.add_all([ProviderHealth(upstream_model_id=item["id"],success_count=index+1,last_success_at=now+timedelta(seconds=index)) for index,item in enumerate(upstreams)])
        unified.combo_strategy="last_known_good";db.commit()
        assert engine.route_candidates(db,request)[1][0].upstream.id==upstreams[2]["id"]

        request.session_key="session-a";engine.remember_session_candidate(unified,request,candidates[0]["id"])
        assert engine.route_candidates(db,request)[1][0].candidate.id==candidates[0]["id"]


def test_exhausted_latest_quota_filters_candidate_with_explicit_reason(client):
    unified_data,upstreams,_=_combo_fixture(client)
    request=CanonicalRequest("chat","openai_chat",unified_data["name"],messages=[{"role":"user","content":"x"}])
    with SessionLocal() as db:
        db.add(QuotaSnapshot(upstream_model_id=upstreams[0]["id"],remaining_requests=0,remaining_tokens=100))
        db.commit()
        _,eligible,explanation=engine.route_candidates(db,request)
        assert all(item.upstream.id!=upstreams[0]["id"] for item in eligible)
        rejected=next(item for item in explanation if item["upstream_model_id"]==upstreams[0]["id"])
        assert rejected["eligible"] is False
        assert "上游额度已耗尽" in rejected["reasons"]


def test_non_combo_mode_ignores_stored_combo_strategy(client,monkeypatch):
    unified_data,upstreams,_=_combo_fixture(client)
    request=CanonicalRequest("chat","openai_chat",unified_data["name"],messages=[{"role":"user","content":"x"}])
    with SessionLocal() as db:
        unified=db.get(UnifiedModel,unified_data["id"])
        unified.routing_mode="static";unified.combo_strategy="weighted";db.commit()
        monkeypatch.setattr(engine.random,"choices",lambda population,weights,k:[population[-1]])
        assert engine.route_candidates(db,request)[1][0].upstream.id==upstreams[0]["id"]


def test_unified_model_context_latency_and_cost_constraints_filter_candidates(client):
    unified_data,upstreams,_=_combo_fixture(client)
    request=CanonicalRequest("chat","openai_chat",unified_data["name"],messages=[{"role":"user","content":"x"}],parameters={"max_tokens":1})
    with SessionLocal() as db:
        unified=db.get(UnifiedModel,unified_data["id"]);unified.min_context_window=4000;unified.max_latency_ms=100;unified.max_cost_per_request=0.00001
        first=db.get(UpstreamModel,upstreams[0]["id"]);first.context_window=1000
        second=db.get(UpstreamModel,upstreams[1]["id"]);second.context_window=8000;second.input_price=1;second.output_price=1
        third=db.get(UpstreamModel,upstreams[2]["id"]);third.context_window=8000;third.input_price=20;third.output_price=20
        db.add(ProviderHealth(upstream_model_id=second.id,avg_latency_ms=200));db.commit()
        try:engine.route_candidates(db,request)
        except ProtocolError as exc:explanation=exc.details["candidates"]
        else:raise AssertionError("all constrained candidates must be rejected")
        reasons={item["upstream_model_id"]:item["reasons"] for item in explanation}
        assert any("上下文窗口" in reason for reason in reasons[first.id])
        assert any("平均延迟" in reason for reason in reasons[second.id])
        assert any("估算成本" in reason for reason in reasons[third.id])
