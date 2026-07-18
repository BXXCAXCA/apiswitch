"""Unified-model execution for OpenAI-compatible moderation requests."""

import time
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, RequestLog
from apiswitch.gateway.errors import GatewayError, NoAvailableCandidateError
from apiswitch.providers.base import ProviderError
from apiswitch.providers.factory import build_selected_provider_adapter
from apiswitch.router.health import record_candidate_failure, record_candidate_success
from apiswitch.router.selector import SelectedCandidate, list_ranked_candidates
from apiswitch.schemas.gateway import ModerationRequest
from apiswitch.services.budget_enforcement import enforce_candidate_budgets
from apiswitch.services.quota_accounting import record_adapter_quota_snapshot
from apiswitch.services.routing_controls import estimate_token_count
from apiswitch.services.session_affinity import record_session_affinity
from apiswitch.services.usage_accounting import record_usage_history


async def execute_moderations(
    request: ModerationRequest,
    db: Session,
    *,
    api_token_id: int | None = None,
    session_key: str | None = None,
    tier: str | None = None,
    max_cost: float | None = None,
) -> dict:
    started = time.perf_counter()
    request_id = f"req_{uuid.uuid4().hex}"
    attempts: list[dict] = []
    input_tokens = estimate_token_count(request.input)
    log = RequestLog(
        request_id=request_id,
        started_at=datetime.utcnow(),
        inbound_protocol="openai_moderations",
        unified_model=request.model,
        success=False,
        cache_hit=False,
        retry_chain_json={"attempts": attempts},
    )
    db.add(log)
    db.flush()
    last_error: ProviderError | None = None
    final_candidate: SelectedCandidate | None = None
    try:
        candidates = list_ranked_candidates(
            db,
            request.model,
            session_key=session_key,
            tier=tier,
            max_cost=max_cost,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=0,
            required_capabilities={"moderations"},
        )
        candidates = enforce_candidate_budgets(
            db, candidates, api_token_id=api_token_id, unified_model=request.model
        )
        for selected in candidates:
            final_candidate = selected
            attempt_started = time.perf_counter()
            try:
                if db.get(Provider, selected.provider_id) is None:
                    raise ProviderError(f"Provider config not found: {selected.provider_id}", "provider_not_found")
                provider = build_selected_provider_adapter(db, selected)
                response = await provider.moderations(
                    request.model_copy(update={"model": selected.upstream_model})
                )
                record_adapter_quota_snapshot(
                    db, provider=provider, provider_connection_id=selected.provider_connection_id
                )
                latency_ms = (time.perf_counter() - attempt_started) * 1000
                total_latency_ms = (time.perf_counter() - started) * 1000
                record_candidate_success(db, selected.candidate_id, latency_ms)
                record_session_affinity(
                    db,
                    unified_model_name=request.model,
                    session_key=session_key,
                    candidate_id=selected.candidate_id,
                    provider_connection_id=selected.provider_connection_id,
                )
                attempts.append(
                    {
                        "candidate_id": selected.candidate_id,
                        "provider": selected.provider_name,
                        "upstream_model": selected.upstream_model,
                        "score": selected.score,
                        "success": True,
                        "latency_ms": round(latency_ms, 2),
                    }
                )
                _, estimated_cost = record_usage_history(
                    db,
                    request_id=request_id,
                    api_token_id=api_token_id,
                    provider_connection_id=selected.provider_connection_id,
                    provider_id=selected.provider_id,
                    unified_model=request.model,
                    upstream_model=selected.upstream_model,
                    input_tokens=input_tokens,
                    output_tokens=0,
                )
                log.finished_at = datetime.utcnow()
                log.final_provider = selected.provider_name
                log.provider_connection_id = selected.provider_connection_id
                log.provider_node_id = selected.provider_node_id
                log.final_upstream_model = selected.upstream_model
                log.success = True
                log.latency_ms = total_latency_ms
                log.input_tokens = input_tokens
                log.output_tokens = 0
                log.estimated_cost = estimated_cost
                log.retry_chain_json = {"attempts": attempts}
                db.commit()
                response["model"] = request.model
                response.setdefault("apiswitch", {}).update(
                    {
                        "request_id": request_id,
                        "provider": selected.provider_name,
                        "upstream_model": selected.upstream_model,
                        "candidate_id": selected.candidate_id,
                        "score": selected.score,
                        "score_breakdown": selected.score_breakdown,
                        "latency_ms": round(total_latency_ms, 2),
                        "estimated_cost": estimated_cost,
                        "retry_chain": attempts,
                    }
                )
                return response
            except ProviderError as exc:
                last_error = exc
                record_candidate_failure(db, selected.candidate_id, str(exc))
                attempts.append(
                    {
                        "candidate_id": selected.candidate_id,
                        "provider": selected.provider_name,
                        "upstream_model": selected.upstream_model,
                        "score": selected.score,
                        "success": False,
                        "error_type": exc.error_type,
                        "error_message": str(exc),
                    }
                )
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
