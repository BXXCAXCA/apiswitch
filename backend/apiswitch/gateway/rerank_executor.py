import time
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from apiswitch.db.models import RequestLog
from apiswitch.gateway.errors import GatewayError, NoAvailableCandidateError
from apiswitch.providers.base import ProviderError
from apiswitch.providers.factory import build_selected_provider_adapter
from apiswitch.router.health import record_candidate_failure, record_candidate_success
from apiswitch.router.selector import list_ranked_candidates
from apiswitch.schemas.gateway import RerankRequest
from apiswitch.services.budget_enforcement import enforce_candidate_budgets
from apiswitch.services.routing_controls import estimate_token_count
from apiswitch.services.usage_accounting import record_usage_history


async def execute_rerank(request: RerankRequest, db: Session, *, api_token_id: int | None = None, session_key: str | None = None, tier: str | None = None, max_cost: float | None = None) -> dict:
    started = time.perf_counter(); request_id = f"req_{uuid.uuid4().hex}"; attempts: list[dict] = []
    tokens = estimate_token_count({"query": request.query, "documents": request.documents})
    log = RequestLog(request_id=request_id, started_at=datetime.utcnow(), inbound_protocol="rerank", unified_model=request.model, success=False, cache_hit=False, retry_chain_json={"attempts": attempts})
    db.add(log); db.flush()
    final = None
    try:
        candidates = enforce_candidate_budgets(db, list_ranked_candidates(db, request.model, session_key=session_key, tier=tier, max_cost=max_cost, estimated_input_tokens=tokens, estimated_output_tokens=0, required_capabilities={"rerank"}), api_token_id=api_token_id, unified_model=request.model)
        last_error = None
        for selected in candidates:
            final = selected; attempt_started = time.perf_counter()
            try:
                provider = build_selected_provider_adapter(db, selected)
                response = await provider.rerank(request.model_copy(update={"model": selected.upstream_model}))
                latency = (time.perf_counter() - attempt_started) * 1000
                record_candidate_success(db, selected.candidate_id, latency)
                attempts.append({"candidate_id": selected.candidate_id, "provider": selected.provider_name, "upstream_model": selected.upstream_model, "success": True, "latency_ms": round(latency, 2)})
                _, cost = record_usage_history(db, request_id=request_id, api_token_id=api_token_id, provider_connection_id=selected.provider_connection_id, provider_id=selected.provider_id, unified_model=request.model, upstream_model=selected.upstream_model, input_tokens=tokens, output_tokens=0)
                log.finished_at = datetime.utcnow(); log.final_provider = selected.provider_name; log.provider_connection_id = selected.provider_connection_id; log.provider_node_id = selected.provider_node_id; log.final_upstream_model = selected.upstream_model; log.success = True; log.latency_ms = (time.perf_counter()-started)*1000; log.input_tokens = tokens; log.output_tokens = 0; log.estimated_cost = cost; log.retry_chain_json = {"attempts": attempts}; db.commit()
                response["model"] = request.model; response.setdefault("apiswitch", {}).update({"request_id": request_id, "provider": selected.provider_name, "upstream_model": selected.upstream_model, "candidate_id": selected.candidate_id, "estimated_cost": cost, "retry_chain": attempts}); return response
            except ProviderError as exc:
                last_error = exc; record_candidate_failure(db, selected.candidate_id, str(exc)); attempts.append({"candidate_id": selected.candidate_id, "success": False, "error_type": exc.error_type, "error_message": str(exc)}); db.flush()
        raise NoAvailableCandidateError(str(last_error) if last_error else "All candidates failed")
    except GatewayError as exc:
        log.finished_at = datetime.utcnow(); log.error_type = exc.error_type; log.error_message = str(exc); log.latency_ms = (time.perf_counter()-started)*1000; log.retry_chain_json = {"attempts": attempts}
        if final: log.final_provider = final.provider_name; log.final_upstream_model = final.upstream_model
        db.commit(); raise
