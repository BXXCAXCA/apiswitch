from __future__ import annotations

import random
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apiswitch.db.models import AuxiliaryModel, AuxiliarySettings, AuxiliaryWorkflow, CircuitBreaker, ProviderHealth, ProviderInstance, QuotaSnapshot, RequestLog, UnifiedModel, UnifiedModelCandidate, UpstreamModel, UsageHistory
from apiswitch.protocols.canonical import CanonicalRequest, ProtocolError


@dataclass
class RouteCandidate:
    candidate: UnifiedModelCandidate
    upstream: UpstreamModel
    provider: ProviderInstance
    reason: list[str]


_round_robin: dict[int,int]={}
_affinity: dict[tuple[int,str],tuple[int,float]]={}
_routing_lock=threading.Lock()


def remember_session_candidate(unified:UnifiedModel,request:CanonicalRequest,candidate_id:int)->None:
    if not unified.session_affinity_enabled or not request.session_key:return
    now=time.monotonic()
    with _routing_lock:
        if len(_affinity)>10_000:
            expired=[key for key,(_,seen) in _affinity.items() if now-seen>3600]
            for key in expired:_affinity.pop(key,None)
        _affinity[(unified.id,request.session_key)]=(candidate_id,now)


def structured_error(error_type: str, message: str, stage: str, request_id: str | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"type": error_type, "message": message, "stage": stage, "request_id": request_id or f"req_{uuid.uuid4().hex}", "details": details or {}}}


def _caps(upstream: UpstreamModel, candidate: UnifiedModelCandidate) -> set[str]:
    overrides = candidate.capability_overrides_json or {}
    return set(overrides.get("input", upstream.input_capabilities_json or [])) | set(overrides.get("output", upstream.output_capabilities_json or []))


def _provider_protocol_supports(provider: ProviderInstance, request: CanonicalRequest) -> bool:
    if provider.protocol_type in {"openai", "openai_compatible"}:
        return request.request_type in {"chat", "embeddings", "images", "audio", "moderations", "rerank", "search", "batches", "video", "music"}
    return request.request_type == "chat" and provider.protocol_type in {"anthropic_messages", "gemini"}


def _estimated_request_cost(request: CanonicalRequest, upstream: UpstreamModel) -> float:
    text=" ".join(str(message.get("content", "")) for message in request.messages if isinstance(message,dict))
    input_tokens=max(1,len(text)//4) if text else 1
    output_tokens=int(request.parameters.get("max_tokens") or upstream.max_output_tokens or 1024)
    return (input_tokens*(upstream.input_price or 0)+output_tokens*(upstream.output_price or 0))/1_000_000


def _applicable_workflows(db: Session, unified: UnifiedModel) -> list[AuxiliaryWorkflow]:
    setting = db.get(AuxiliarySettings, 1) or AuxiliarySettings(mode="global_pool")
    if setting.mode == "disabled": return []
    workflows = list(db.scalars(select(AuxiliaryWorkflow).where(AuxiliaryWorkflow.enabled.is_(True)).order_by(AuxiliaryWorkflow.priority,AuxiliaryWorkflow.id)).all())
    if setting.mode == "per_unified_model": return [item for item in workflows if item.unified_model_id == unified.id]
    return [item for item in workflows if item.unified_model_id is None and item.scope == "global"]


def route_candidates(db: Session, request: CanonicalRequest) -> tuple[UnifiedModel, list[RouteCandidate], list[dict[str, Any]]]:
    unified = db.scalar(select(UnifiedModel).where(UnifiedModel.name == request.unified_model, UnifiedModel.enabled.is_(True)))
    if not unified: raise ProtocolError("provider_unavailable", "统一模型不存在或未启用", "model_lookup")
    enabled_protocols = set(unified.enabled_protocols_json or [])
    if request.inbound_protocol not in enabled_protocols:
        raise ProtocolError("protocol_not_enabled", "统一模型未开启该入口协议", "protocol_check", {"protocol": request.inbound_protocol})
    declared=unified.required_capabilities_json or {}
    expected = set(request.required_input + request.required_output)
    if isinstance(declared,dict):
        expected.update(declared.get("input",[]));expected.update(declared.get("output",[]))
    workflows = _applicable_workflows(db, unified)
    assisted_capabilities = {capability for workflow in workflows for capability in (workflow.input_capability, workflow.output_capability)}
    rows = db.execute(select(UnifiedModelCandidate, UpstreamModel, ProviderInstance).join(UpstreamModel, UnifiedModelCandidate.upstream_model_id == UpstreamModel.id).join(ProviderInstance, UpstreamModel.provider_instance_id == ProviderInstance.id).where(UnifiedModelCandidate.unified_model_id == unified.id)).all()
    upstream_ids=[upstream.id for _,upstream,_ in rows]
    latest_quotas:dict[int,QuotaSnapshot]={}
    for quota in db.scalars(select(QuotaSnapshot).where(QuotaSnapshot.upstream_model_id.in_(upstream_ids)).order_by(QuotaSnapshot.captured_at.desc(),QuotaSnapshot.id.desc())).all():
        latest_quotas.setdefault(quota.upstream_model_id,quota)
    eligible: list[RouteCandidate] = []; explanation: list[dict[str, Any]] = []
    for candidate, upstream, provider in rows:
        reasons: list[str] = []
        breaker = db.scalar(select(CircuitBreaker).where(CircuitBreaker.upstream_model_id == upstream.id))
        if not candidate.enabled: reasons.append("候选已停用")
        if not provider.enabled: reasons.append("供应商实例已停用")
        if not upstream.enabled: reasons.append("上游模型已停用")
        if upstream.remote_status == "missing": reasons.append("远端模型已消失")
        if not _provider_protocol_supports(provider,request):reasons.append("供应商协议无法可靠执行该请求类型")
        if breaker and breaker.state == "open":
            if breaker.opened_at and datetime.utcnow() >= breaker.opened_at + timedelta(seconds=breaker.cooldown_seconds or 60):
                breaker.state="half_open";breaker.half_open_at=datetime.utcnow();db.add(breaker)
            else:reasons.append("熔断器已开启")
        quota=latest_quotas.get(upstream.id)
        quota_values=[value for value in ((quota.remaining_requests if quota else None),(quota.remaining_tokens if quota else None),(quota.remaining_credit if quota else None)) if value is not None]
        if any(value<=0 for value in quota_values):reasons.append("上游额度已耗尽")
        if unified.min_context_window and (upstream.context_window is None or upstream.context_window<unified.min_context_window):reasons.append(f"上下文窗口小于 {unified.min_context_window}")
        health=db.scalar(select(ProviderHealth).where(ProviderHealth.upstream_model_id==upstream.id))
        if unified.max_latency_ms and health and health.avg_latency_ms is not None and health.avg_latency_ms>unified.max_latency_ms:reasons.append(f"平均延迟超过 {unified.max_latency_ms} ms")
        if unified.max_cost_per_request is not None and _estimated_request_cost(request,upstream)>unified.max_cost_per_request:reasons.append("估算成本超过统一模型单次上限")
        gaps = expected - _caps(upstream, candidate)
        assisted = sorted(gaps & assisted_capabilities)
        unsupported = sorted(gaps - assisted_capabilities)
        if unsupported: reasons.append("能力不足：" + ", ".join(unsupported))
        explanation.append({"candidate_id": candidate.id, "upstream_model_id": upstream.id, "provider_instance_id": provider.id, "eligible": not reasons, "reasons": reasons, "assisted_capabilities": assisted, "priority": candidate.priority, "weight": candidate.weight})
        if not reasons: eligible.append(RouteCandidate(candidate, upstream, provider, ["辅助工作流覆盖：" + ", ".join(assisted)] if assisted else ["能力、启用状态、远端状态均满足"] ))
    if not eligible:
        if explanation and all("熔断器已开启" in item.get("reasons", []) for item in explanation):
            raise ProtocolError("provider_unavailable", "统一模型的全部候选均处于熔断冷却期", "circuit_breaker", {"candidates": explanation})
        raise ProtocolError("capability_not_supported", "没有已配置的候选可满足请求能力", "capability_check", {"candidates": explanation})
    # Static/auto routing must not accidentally retain an editable Combo
    # strategy from an earlier configuration. Their deterministic fallback is
    # priority; Combo is the only mode that applies weighted/rotating policies.
    strategy=unified.combo_strategy if unified.routing_mode=="combo" else "priority";eligible.sort(key=lambda item:(item.candidate.priority,item.candidate.id))
    if strategy=="weighted" and len(eligible)>1:
        weights=[max(item.candidate.weight,0) for item in eligible]
        if any(weights):first=random.choices(eligible,weights=weights,k=1)[0];eligible=[first,*[item for item in eligible if item is not first]]
    elif strategy=="round_robin" and len(eligible)>1:
        with _routing_lock:index=_round_robin.get(unified.id,0)%len(eligible);_round_robin[unified.id]=index+1
        eligible=eligible[index:]+eligible[:index]
    elif strategy=="least_used":
        counts=dict(db.execute(select(UsageHistory.upstream_model_id,func.count(UsageHistory.id)).where(UsageHistory.upstream_model_id.in_([item.upstream.id for item in eligible])).group_by(UsageHistory.upstream_model_id)).all())
        eligible.sort(key=lambda item:(counts.get(item.upstream.id,0),item.candidate.priority,item.candidate.id))
    elif strategy=="cost_optimized":eligible.sort(key=lambda item:((item.upstream.input_price or 0)+(item.upstream.output_price or 0),item.candidate.priority,item.candidate.id))
    elif strategy=="quota_headroom":
        def headroom(item):
            row=latest_quotas.get(item.upstream.id)
            values=[value for value in ((row.remaining_credit if row else None),(row.remaining_tokens if row else None),(row.remaining_requests if row else None)) if value is not None]
            return max(values) if values else float("-inf")
        eligible.sort(key=lambda item:(-headroom(item),item.candidate.priority,item.candidate.id))
    elif strategy=="last_known_good":
        health={row.upstream_model_id:row for row in db.scalars(select(ProviderHealth).where(ProviderHealth.upstream_model_id.in_([item.upstream.id for item in eligible]))).all()}
        eligible.sort(key=lambda item:((health.get(item.upstream.id).last_success_at if health.get(item.upstream.id) and health.get(item.upstream.id).last_success_at else datetime.min),(health.get(item.upstream.id).success_count or 0) if health.get(item.upstream.id) else 0),reverse=True)
    if unified.session_affinity_enabled and request.session_key:
        with _routing_lock:remembered=_affinity.get((unified.id,request.session_key))
        if remembered:
            match=next((item for item in eligible if item.candidate.id==remembered[0]),None)
            if match:eligible=[match,*[item for item in eligible if item is not match]]
    return unified, eligible, explanation


def plan_auxiliary(db: Session, request: CanonicalRequest, unified: UnifiedModel) -> dict[str, Any]:
    setting = db.get(AuxiliarySettings, 1) or AuxiliarySettings(mode="global_pool")
    if setting.mode == "disabled": return {"mode": "disabled", "steps": []}
    workflows = _applicable_workflows(db, unified)
    requested = set(request.required_input + request.required_output)
    selected=[]
    for workflow in workflows:
        if workflow.workflow_type=="structured_repair":applicable="json" in request.required_output
        elif workflow.workflow_type=="terminal_capability":applicable=workflow.output_capability in request.required_output
        else:applicable=workflow.input_capability in requested
        if applicable:selected.append(workflow)
    steps: list[dict[str, Any]] = []
    for workflow in selected:
        specifications = workflow.ordered_steps_json or [{"input": workflow.input_capability, "output": workflow.output_capability}]
        for index, specification in enumerate(specifications):
            required = str(specification.get("model_capability") or specification.get("input") or workflow.input_capability)
            pool = list(db.scalars(select(AuxiliaryModel).where(AuxiliaryModel.enabled.is_(True), AuxiliaryModel.unified_model_id == (unified.id if setting.mode == "per_unified_model" else None)).order_by(AuxiliaryModel.priority, AuxiliaryModel.id)).all())
            aux = next((item for item in pool if required in set(item.capabilities_json or [])), None)
            if aux is None: raise ProtocolError("auxiliary_workflow_not_configured", "辅助工作流步骤没有配置匹配能力的辅助上游模型", "auxiliary_plan", {"workflow_id": workflow.id, "step_index": index, "required_capability": required})
            upstream=db.get(UpstreamModel,aux.upstream_model_id);provider=db.get(ProviderInstance,upstream.provider_instance_id) if upstream else None
            if not upstream or not provider or not upstream.enabled or not provider.enabled or upstream.remote_status=="missing":raise ProtocolError("auxiliary_workflow_not_configured","辅助工作流引用的上游模型不可用","auxiliary_plan",{"workflow_id":workflow.id,"step_index":index,"upstream_model_id":aux.upstream_model_id})
            steps.append({"workflow_id":workflow.id,"workflow_type":workflow.workflow_type,"step_index":index,"auxiliary_model_id":aux.id,"upstream_model_id":aux.upstream_model_id,"provider_instance_id":provider.id,"status":"planned",**specification})
    return {"mode": setting.mode, "steps": steps}


def protocol_matrix(db: Session, unified_id: int) -> list[dict[str, Any]]:
    unified = db.get(UnifiedModel, unified_id)
    if not unified: raise ProtocolError("validation_error", "统一模型不存在", "validation")
    protocols = ["openai_chat", "openai_responses", "anthropic_messages", "gemini_v1beta", "embeddings", "files", "images", "audio", "moderations", "rerank", "search", "batches", "websocket", "video", "music"]
    enabled = set(unified.enabled_protocols_json or [])
    required={"openai_chat":"text","openai_responses":"text","anthropic_messages":"text","gemini_v1beta":"text","embeddings":"embeddings","files":"files","images":"images","audio":"audio","moderations":"moderation","rerank":"rerank","search":"search","batches":"text","websocket":"text","video":"video","music":"music"}
    native={"openai_chat":{"openai","openai_compatible"},"openai_responses":{"openai"},"anthropic_messages":{"anthropic_messages"},"gemini_v1beta":{"gemini"}}
    rows=db.execute(select(UnifiedModelCandidate,UpstreamModel,ProviderInstance).join(UpstreamModel,UnifiedModelCandidate.upstream_model_id==UpstreamModel.id).join(ProviderInstance,UpstreamModel.provider_instance_id==ProviderInstance.id).where(UnifiedModelCandidate.unified_model_id==unified.id,UnifiedModelCandidate.enabled.is_(True),UpstreamModel.enabled.is_(True),ProviderInstance.enabled.is_(True))).all()
    workflow_caps={cap for workflow in _applicable_workflows(db,unified) for cap in (workflow.input_capability,workflow.output_capability)}
    matrix=[]
    for protocol in protocols:
        if protocol not in enabled:matrix.append({"protocol":protocol,"status":"unsupported","reason":"统一模型未开启入口协议","candidates":[]});continue
        capability=required[protocol];candidate_states=[]
        for candidate,upstream,provider in rows:
            supports=capability in _caps(upstream,candidate) or (capability=="files" and "text" in _caps(upstream,candidate))
            candidate_states.append({"candidate_id":candidate.id,"upstream_model_id":upstream.id,"provider_protocol":provider.protocol_type,"supports":supports})
        direct=[item for item in candidate_states if item["supports"]]
        if any(item["provider_protocol"] in native.get(protocol,set()) for item in direct):status="native";reason="至少一个候选原生支持入口协议和能力"
        elif direct:status="lossless";reason="候选能力满足且存在可靠协议转换"
        elif capability in workflow_caps:status="assisted";reason="主候选能力不足，已配置辅助工作流覆盖"
        else:status="unsupported";reason="没有候选或辅助工作流可满足所需能力"
        matrix.append({"protocol":protocol,"status":status,"reason":reason,"required_capability":capability,"candidates":candidate_states})
    return matrix


def execute_mock(db: Session, request: CanonicalRequest, api_token_id: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    request_id = f"req_{uuid.uuid4().hex}"
    started = datetime.utcnow()
    try:
        unified, candidates, explanation = route_candidates(db, request)
        auxiliary = plan_auxiliary(db, request, unified)
        selected = candidates[0]
        log = RequestLog(request_id=request_id, started_at=started, finished_at=datetime.utcnow(), inbound_protocol=request.inbound_protocol, unified_model=request.unified_model, provider_instance_id=selected.provider.id, upstream_model_id=selected.upstream.id, combo_strategy=unified.combo_strategy, candidate_summary_json=explanation, auxiliary_summary_json=auxiliary, api_token_id=api_token_id, success=True, latency_ms=0)
        db.add(log); db.commit()
        upstream_request = {"protocol": selected.provider.protocol_type, "model": selected.upstream.model_id, "canonical": request.dump()}
        return {"request_id": request_id, "selected": selected, "upstream_request": upstream_request, "auxiliary": auxiliary, "explanation": explanation}, {"text": "Mock upstream response"}
    except ProtocolError as exc:
        db.add(RequestLog(request_id=request_id, started_at=started, finished_at=datetime.utcnow(), inbound_protocol=request.inbound_protocol, unified_model=request.unified_model, success=False, error_type=exc.error_type, error_message=str(exc), failure_stage=exc.stage, api_token_id=api_token_id)); db.commit()
        raise
