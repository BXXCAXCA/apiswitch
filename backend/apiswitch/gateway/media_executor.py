"""Shared Unified-Model execution for asynchronous media-generation requests."""

import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, RequestLog
from apiswitch.gateway.errors import GatewayError, NoAvailableCandidateError
from apiswitch.providers.base import ProviderError
from apiswitch.providers.factory import build_selected_provider_adapter
from apiswitch.router.health import record_candidate_failure, record_candidate_success
from apiswitch.router.selector import SelectedCandidate, list_ranked_candidates
from apiswitch.schemas.gateway import MusicGenerationRequest, VideoGenerationRequest
from apiswitch.services.budget_enforcement import enforce_candidate_budgets
from apiswitch.services.quota_accounting import record_adapter_quota_snapshot
from apiswitch.services.routing_controls import estimate_token_count
from apiswitch.services.session_affinity import record_session_affinity
from apiswitch.services.usage_accounting import record_usage_history

MediaRequest = VideoGenerationRequest | MusicGenerationRequest


async def execute_media_generation(
    request: MediaRequest,
    db: Session,
    *,
    capability: str,
    provider_method: str,
    inbound_protocol: str,
    api_token_id: int | None = None,
    session_key: str | None = None,
    tier: str | None = None,
    max_cost: float | None = None,
) -> dict[str, Any]:
    started_at = datetime.utcnow()
    started = time.perf_counter()
    request_id = f"req_{uuid.uuid4().hex}"
    attempts: list[dict[str, Any]] = []
    input_tokens = estimate_token_count(request.prompt)
    log = RequestLog(
        request_id=request_id,
        started_at=started_at,
        inbound_protocol=inbound_protocol,
        unified_model=request.model,
        success=False,
        cache_hit=False,
        retry_chain_json={"attempts": attempts},
    )
    db.add(log)
    db.flush()
    final_candidate: SelectedCandidate | None = None
    last_error: ProviderError | None = None

    try:
        candidates = list_ranked_candidates(
            db,
            request.model,
            session_key=session_key,
            tier=tier,
            max_cost=max_cost,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=0,
            required_capabilities={capability},
        )
        candidates = enforce_candidate_budgets(db, candidates, api_token_id=api_token_id, unified_model=request.model)
        for selected in candidates:
            final_candidate = selected
            attempt_started = time.perf_counter()
            try:
                if db.get(Provider, selected.provider_id) is None:
                    raise ProviderError(f"Provider config not found: {selected.provider_id}", "provider_not_found")
                provider = build_selected_provider_adapter(db, selected)
                response = await getattr(provider, provider_method)(
                    request.model_copy(update={"model": selected.upstream_model})
                )
                record_adapter_quota_snapshot(db, provider=provider, provider_connection_id=selected.provider_connection_id)
                attempt_latency_ms = (time.perf_counter() - attempt_started) * 1000
                record_candidate_success(db, selected.candidate_id, attempt_latency_ms)
                record_session_affinity(
                    db,
                    unified_model_name=request.model,
                    session_key=session_key,
                    candidate_id=selected.candidate_id,
                    provider_connection_id=selected.provider_connection_id,
                )
                attempts.append({
                    "candidate_id": selected.candidate_id,
                    "provider": selected.provider_name,
                    "upstream_model": selected.upstream_model,
                    "score": selected.score,
                    "success": True,
                    "latency_ms": round(attempt_latency_ms, 2),
                })
                usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
                output_tokens = usage.get("completion_tokens", 0)
                _, estimated_cost = record_usage_history(
                    db,
                    request_id=request_id,
                    api_token_id=api_token_id,
                    provider_connection_id=selected.provider_connection_id,
                    provider_id=selected.provider_id,
                    unified_model=request.model,
                    upstream_model=selected.upstream_model,
                    input_tokens=usage.get("prompt_tokens", input_tokens),
                    output_tokens=output_tokens,
                )
                log.finished_at = datetime.utcnow()
                log.final_provider = selected.provider_name
                log.provider_connection_id = selected.provider_connection_id
                log.provider_node_id = selected.provider_node_id
                log.final_upstream_model = selected.upstream_model
                log.success = True
                log.latency_ms = (time.perf_counter() - started) * 1000
                log.input_tokens = usage.get("prompt_tokens", input_tokens)
                log.output_tokens = output_tokens
                log.estimated_cost = estimated_cost
                log.retry_chain_json = {"attempts": attempts}
                db.commit()
                response["model"] = request.model
                response.setdefault("apiswitch", {}).update({
                    "request_id": request_id,
                    "provider": selected.provider_name,
                    "upstream_model": selected.upstream_model,
                    "candidate_id": selected.candidate_id,
                    "score": selected.score,
                    "score_breakdown": selected.score_breakdown,
                    "latency_ms": round(log.latency_ms, 2),
                    "estimated_cost": estimated_cost,
                    "retry_chain": attempts,
                })
                return response
            except ProviderError as exc:
                last_error = exc
                record_candidate_failure(db, selected.candidate_id, str(exc))
                attempts.append({
                    "candidate_id": selected.candidate_id,
                    "provider": selected.provider_name,
                    "upstream_model": selected.upstream_model,
                    "score": selected.score,
                    "success": False,
                    "error_type": exc.error_type,
                    "error_message": str(exc),
                })
                db.flush()
        raise NoAvailableCandidateError(str(last_error) if last_error else "All candidates failed")
    except GatewayError as exc:
        log.finished_at = datetime.utcnow()
        log.success = False
        log.error_type = exc.error_type
        log.error_message = str(exc)
        log.latency_ms = (time.perf_counter() - started) * 1000
        log.retry_chain_json = {"attempts": attempts}
        if final_candidate is not None:
            log.final_provider = final_candidate.provider_name
            log.final_upstream_model = final_candidate.upstream_model
        db.commit()
        raise


async def execute_video_generation(request: VideoGenerationRequest, db: Session, **kwargs: Any) -> dict[str, Any]:
    return await execute_media_generation(
        request, db, capability="video", provider_method="video_generations", inbound_protocol="video_generations", **kwargs
    )


async def execute_music_generation(request: MusicGenerationRequest, db: Session, **kwargs: Any) -> dict[str, Any]:
    return await execute_media_generation(
        request, db, capability="music", provider_method="music_generations", inbound_protocol="music_generations", **kwargs
    )
