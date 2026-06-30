import time
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from apiswitch.db.models import RequestLog
from apiswitch.gateway.errors import GatewayError
from apiswitch.providers.base import ProviderError
from apiswitch.providers.registry import provider_registry
from apiswitch.router.selector import select_best_candidate
from apiswitch.schemas.gateway import ChatCompletionRequest


class GatewayExecutor:
    async def execute_chat_completion(self, request: ChatCompletionRequest, db: Session) -> dict:
        started_at = datetime.utcnow()
        start_time = time.perf_counter()
        request_id = f"req_{uuid.uuid4().hex}"
        selected = None
        log = RequestLog(
            request_id=request_id,
            started_at=started_at,
            inbound_protocol="openai_chat",
            unified_model=request.model,
            success=False,
            cache_hit=False,
            retry_chain_json={"attempts": []},
        )
        db.add(log)
        db.flush()

        try:
            selected = select_best_candidate(db, request.model)
            provider = provider_registry.get(selected.provider_type)
            response = await provider.chat(request)
            latency_ms = (time.perf_counter() - start_time) * 1000

            log.finished_at = datetime.utcnow()
            log.final_provider = selected.provider_name
            log.final_upstream_model = selected.upstream_model
            log.success = True
            log.latency_ms = latency_ms
            log.retry_chain_json = {
                "attempts": [
                    {
                        "candidate_id": selected.candidate_id,
                        "provider": selected.provider_name,
                        "upstream_model": selected.upstream_model,
                        "score": selected.score,
                        "success": True,
                    }
                ]
            }
            usage = response.get("usage", {})
            log.input_tokens = usage.get("prompt_tokens")
            log.output_tokens = usage.get("completion_tokens")
            db.commit()

            response.setdefault("apiswitch", {})
            response["apiswitch"].update(
                {
                    "request_id": request_id,
                    "provider": selected.provider_name,
                    "upstream_model": selected.upstream_model,
                    "candidate_id": selected.candidate_id,
                    "score": selected.score,
                    "latency_ms": round(latency_ms, 2),
                }
            )
            return response
        except (GatewayError, ProviderError) as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            log.finished_at = datetime.utcnow()
            log.success = False
            log.error_type = getattr(exc, "error_type", "gateway_error")
            log.error_message = str(exc)
            log.latency_ms = latency_ms
            if selected is not None:
                log.final_provider = selected.provider_name
                log.final_upstream_model = selected.upstream_model
            db.commit()
            raise


gateway_executor = GatewayExecutor()
