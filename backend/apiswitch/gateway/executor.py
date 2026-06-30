import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, RequestLog
from apiswitch.gateway.errors import GatewayError, NoAvailableCandidateError
from apiswitch.gateway.streaming import rewrite_openai_sse_model
from apiswitch.providers.base import ProviderError
from apiswitch.providers.factory import build_provider_adapter
from apiswitch.router.health import record_candidate_failure, record_candidate_success
from apiswitch.router.selector import SelectedCandidate, list_ranked_candidates
from apiswitch.schemas.gateway import AnthropicMessagesRequest, ChatCompletionRequest


class GatewayExecutor:
    async def execute_chat_completion(self, request: ChatCompletionRequest, db: Session) -> dict:
        started_at = datetime.utcnow()
        start_time = time.perf_counter()
        request_id = f"req_{uuid.uuid4().hex}"
        last_error: Exception | None = None
        final_candidate: SelectedCandidate | None = None
        attempts: list[dict] = []
        log = RequestLog(
            request_id=request_id,
            started_at=started_at,
            inbound_protocol="openai_chat",
            unified_model=request.model,
            success=False,
            cache_hit=False,
            retry_chain_json={"attempts": attempts},
        )
        db.add(log)
        db.flush()

        try:
            candidates = list_ranked_candidates(db, request.model)
            for selected in candidates:
                final_candidate = selected
                attempt_started = time.perf_counter()
                try:
                    provider_config = db.get(Provider, selected.provider_id)
                    if provider_config is None:
                        raise ProviderError(
                            f"Provider config not found: {selected.provider_id}",
                            "provider_not_found",
                        )
                    provider = build_provider_adapter(provider_config)
                    upstream_request = request.model_copy(update={"model": selected.upstream_model})
                    response = await provider.chat(upstream_request)
                    attempt_latency_ms = (time.perf_counter() - attempt_started) * 1000
                    total_latency_ms = (time.perf_counter() - start_time) * 1000
                    record_candidate_success(db, selected.candidate_id, attempt_latency_ms)

                    attempts.append(
                        {
                            "candidate_id": selected.candidate_id,
                            "provider": selected.provider_name,
                            "upstream_model": selected.upstream_model,
                            "score": selected.score,
                            "success": True,
                            "latency_ms": round(attempt_latency_ms, 2),
                        }
                    )
                    log.finished_at = datetime.utcnow()
                    log.final_provider = selected.provider_name
                    log.final_upstream_model = selected.upstream_model
                    log.success = True
                    log.latency_ms = total_latency_ms
                    log.retry_chain_json = {"attempts": attempts}
                    usage = response.get("usage", {})
                    log.input_tokens = usage.get("prompt_tokens")
                    log.output_tokens = usage.get("completion_tokens")
                    db.commit()

                    response["model"] = request.model
                    response.setdefault("apiswitch", {})
                    response["apiswitch"].update(
                        {
                            "request_id": request_id,
                            "provider": selected.provider_name,
                            "upstream_model": selected.upstream_model,
                            "candidate_id": selected.candidate_id,
                            "score": selected.score,
                            "latency_ms": round(total_latency_ms, 2),
                            "retry_chain": attempts,
                        }
                    )
                    return response
                except ProviderError as exc:
                    last_error = exc
                    reason = str(exc)
                    record_candidate_failure(db, selected.candidate_id, reason)
                    attempts.append(
                        {
                            "candidate_id": selected.candidate_id,
                            "provider": selected.provider_name,
                            "upstream_model": selected.upstream_model,
                            "score": selected.score,
                            "success": False,
                            "error_type": exc.error_type,
                            "error_message": reason,
                        }
                    )
                    db.flush()

            raise NoAvailableCandidateError(str(last_error) if last_error else "All candidates failed")
        except GatewayError as exc:
            total_latency_ms = (time.perf_counter() - start_time) * 1000
            log.finished_at = datetime.utcnow()
            log.success = False
            log.error_type = exc.error_type
            log.error_message = str(exc)
            log.latency_ms = total_latency_ms
            log.retry_chain_json = {"attempts": attempts}
            if final_candidate is not None:
                log.final_provider = final_candidate.provider_name
                log.final_upstream_model = final_candidate.upstream_model
            db.commit()
            raise

    async def execute_messages(self, request: AnthropicMessagesRequest, db: Session) -> dict:
        start_time = time.perf_counter()
        request_id = f"req_{uuid.uuid4().hex}"
        last_error: Exception | None = None
        final_candidate: SelectedCandidate | None = None
        attempts: list[dict] = []
        log = RequestLog(
            request_id=request_id,
            started_at=datetime.utcnow(),
            inbound_protocol="anthropic_messages",
            unified_model=request.model,
            success=False,
            cache_hit=False,
            retry_chain_json={"attempts": attempts},
        )
        db.add(log)
        db.flush()

        try:
            candidates = list_ranked_candidates(db, request.model)
            for selected in candidates:
                final_candidate = selected
                attempt_started = time.perf_counter()
                try:
                    provider_config = db.get(Provider, selected.provider_id)
                    if provider_config is None:
                        raise ProviderError(
                            f"Provider config not found: {selected.provider_id}",
                            "provider_not_found",
                        )
                    provider = build_provider_adapter(provider_config)
                    upstream_request = request.model_copy(update={"model": selected.upstream_model})
                    response = await provider.messages(upstream_request)
                    attempt_latency_ms = (time.perf_counter() - attempt_started) * 1000
                    total_latency_ms = (time.perf_counter() - start_time) * 1000
                    record_candidate_success(db, selected.candidate_id, attempt_latency_ms)
                    attempts.append(
                        {
                            "candidate_id": selected.candidate_id,
                            "provider": selected.provider_name,
                            "upstream_model": selected.upstream_model,
                            "score": selected.score,
                            "success": True,
                            "latency_ms": round(attempt_latency_ms, 2),
                        }
                    )
                    log.finished_at = datetime.utcnow()
                    log.final_provider = selected.provider_name
                    log.final_upstream_model = selected.upstream_model
                    log.success = True
                    log.latency_ms = total_latency_ms
                    log.retry_chain_json = {"attempts": attempts}
                    usage = response.get("usage", {})
                    log.input_tokens = usage.get("input_tokens")
                    log.output_tokens = usage.get("output_tokens")
                    db.commit()

                    response["model"] = request.model
                    response.setdefault("apiswitch", {})
                    response["apiswitch"].update(
                        {
                            "request_id": request_id,
                            "provider": selected.provider_name,
                            "upstream_model": selected.upstream_model,
                            "candidate_id": selected.candidate_id,
                            "score": selected.score,
                            "latency_ms": round(total_latency_ms, 2),
                            "retry_chain": attempts,
                        }
                    )
                    return response
                except ProviderError as exc:
                    last_error = exc
                    reason = str(exc)
                    record_candidate_failure(db, selected.candidate_id, reason)
                    attempts.append(
                        {
                            "candidate_id": selected.candidate_id,
                            "provider": selected.provider_name,
                            "upstream_model": selected.upstream_model,
                            "score": selected.score,
                            "success": False,
                            "error_type": exc.error_type,
                            "error_message": reason,
                        }
                    )
                    db.flush()
            raise NoAvailableCandidateError(str(last_error) if last_error else "All candidates failed")
        except GatewayError as exc:
            log.finished_at = datetime.utcnow()
            log.success = False
            log.error_type = exc.error_type
            log.error_message = str(exc)
            log.latency_ms = (time.perf_counter() - start_time) * 1000
            log.retry_chain_json = {"attempts": attempts}
            if final_candidate is not None:
                log.final_provider = final_candidate.provider_name
                log.final_upstream_model = final_candidate.upstream_model
            db.commit()
            raise

    async def stream_chat_completion(self, request: ChatCompletionRequest, db: Session) -> AsyncIterator[bytes]:
        started_at = datetime.utcnow()
        start_time = time.perf_counter()
        request_id = f"req_{uuid.uuid4().hex}"
        attempts: list[dict] = []
        log = RequestLog(
            request_id=request_id,
            started_at=started_at,
            inbound_protocol="openai_chat_stream",
            unified_model=request.model,
            success=False,
            cache_hit=False,
            retry_chain_json={"attempts": attempts},
        )
        db.add(log)
        db.flush()
        candidates = list_ranked_candidates(db, request.model)

        async def generator() -> AsyncIterator[bytes]:
            last_error: ProviderError | None = None
            final_candidate: SelectedCandidate | None = None
            for selected in candidates:
                final_candidate = selected
                attempt_started = time.perf_counter()
                stream_started = False
                try:
                    provider_config = db.get(Provider, selected.provider_id)
                    if provider_config is None:
                        raise ProviderError(
                            f"Provider config not found: {selected.provider_id}",
                            "provider_not_found",
                        )
                    provider = build_provider_adapter(provider_config)
                    upstream_request = request.model_copy(update={"model": selected.upstream_model, "stream": True})
                    metadata = {
                        "request_id": request_id,
                        "provider": selected.provider_name,
                        "upstream_model": selected.upstream_model,
                        "candidate_id": selected.candidate_id,
                        "score": selected.score,
                    }
                    async for chunk in rewrite_openai_sse_model(
                        provider.stream_chat(upstream_request),
                        request.model,
                        metadata,
                    ):
                        stream_started = True
                        yield chunk

                    attempt_latency_ms = (time.perf_counter() - attempt_started) * 1000
                    total_latency_ms = (time.perf_counter() - start_time) * 1000
                    record_candidate_success(db, selected.candidate_id, attempt_latency_ms)
                    attempts.append(
                        {
                            "candidate_id": selected.candidate_id,
                            "provider": selected.provider_name,
                            "upstream_model": selected.upstream_model,
                            "score": selected.score,
                            "success": True,
                            "latency_ms": round(attempt_latency_ms, 2),
                        }
                    )
                    log.finished_at = datetime.utcnow()
                    log.final_provider = selected.provider_name
                    log.final_upstream_model = selected.upstream_model
                    log.success = True
                    log.latency_ms = total_latency_ms
                    log.retry_chain_json = {"attempts": attempts}
                    db.commit()
                    return
                except ProviderError as exc:
                    last_error = exc
                    reason = str(exc)
                    record_candidate_failure(db, selected.candidate_id, reason)
                    attempts.append(
                        {
                            "candidate_id": selected.candidate_id,
                            "provider": selected.provider_name,
                            "upstream_model": selected.upstream_model,
                            "score": selected.score,
                            "success": False,
                            "error_type": exc.error_type,
                            "error_message": reason,
                        }
                    )
                    db.flush()
                    if stream_started:
                        log.finished_at = datetime.utcnow()
                        log.final_provider = selected.provider_name
                        log.final_upstream_model = selected.upstream_model
                        log.success = False
                        log.error_type = exc.error_type
                        log.error_message = reason
                        log.latency_ms = (time.perf_counter() - start_time) * 1000
                        log.retry_chain_json = {"attempts": attempts}
                        db.commit()
                        yield f"event: error\ndata: {reason}\n\n".encode("utf-8")
                        yield b"data: [DONE]\n\n"
                        return
                    continue

            reason = str(last_error) if last_error else "All streaming candidates failed"
            log.finished_at = datetime.utcnow()
            log.success = False
            log.error_type = getattr(last_error, "error_type", "no_available_candidate")
            log.error_message = reason
            log.latency_ms = (time.perf_counter() - start_time) * 1000
            log.retry_chain_json = {"attempts": attempts}
            if final_candidate is not None:
                log.final_provider = final_candidate.provider_name
                log.final_upstream_model = final_candidate.upstream_model
            db.commit()
            yield f"event: error\ndata: {reason}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"

        return generator()


gateway_executor = GatewayExecutor()
