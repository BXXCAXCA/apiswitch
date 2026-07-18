from __future__ import annotations

from uuid import uuid4


def _provider(client, **overrides):
    payload={"name":f"provider-{uuid4().hex}","template_key":"openai","base_url":"mock://provider","api_key":"unit-placeholder"}
    payload.update(overrides)
    response=client.post("/api/admin/provider-instances",json=payload)
    assert response.status_code==201,response.text
    return response.json()


def test_template_catalog_has_required_metadata_and_truthful_validation_labels(client):
    templates=client.get("/api/admin/provider-templates").json()
    required={"openai","anthropic","gemini","sensenova","ollama","lm_studio","vllm","localai","llama_cpp","azure_openai","vertex_ai","bedrock","openrouter","xai","mistral","cohere","deepseek","groq","together","fireworks","siliconflow","dashscope","zhipu","moonshot","volcengine","minimax","minimax_global","qianfan","hunyuan","modelscope","modelscope_local","cerebras","sambanova","nvidia_nim","perplexity","cloudflare_workers_ai","huggingface","github_models","deepinfra","replicate","fal","novita","featherless","nscale","ovh","scaleway","wavespeed"}
    by_key={item["key"]:item for item in templates}
    assert required<=set(by_key)
    for key in required:
        expected_status={"ollama":"compatible","lm_studio":"compatible","vllm":"compatible","localai":"compatible","llama_cpp":"compatible"}.get(key,"unverified")
        assert by_key[key]["verification_status"] == expected_status
        assert by_key[key]["docs_url"].startswith("https://")
        assert "auth_type" in by_key[key] and "model_list_path" in by_key[key]
    assert "mock" not in by_key
    assert by_key["minimax"]["base_url"] == "https://api.minimaxi.com/v1"
    assert by_key["minimax_global"]["base_url"] == "https://api.minimax.io/v1"
    assert by_key["cohere"]["base_url"] == "https://api.cohere.ai/compatibility/v1"
    assert by_key["perplexity"]["base_url"] == "https://api.perplexity.ai/v1"
    assert by_key["novita"]["base_url"] == "https://api.novita.ai/openai/v1"
    assert by_key["modelscope"]["base_url"] == "https://api-inference.modelscope.cn/v1"
    assert by_key["cloudflare_workers_ai"]["base_url"].endswith("/accounts/YOUR-ACCOUNT-ID/ai/v1")
    assert by_key["vertex_ai"]["base_url"].endswith("/locations/REGION/endpoints/openapi")
    assert by_key["bedrock"]["base_url"] == "https://bedrock-mantle.REGION.api.aws/v1"
    for key in {"replicate", "fal", "wavespeed"}:
        assert by_key[key]["protocol_type"] == "custom"
        assert by_key[key]["model_list_path"] == ""
    assert [item["key"] for item in templates[:4]] == ["manual", "manual_anthropic", "manual_gemini", "manual_custom"]
    assert {item["protocol_type"] for item in templates[:4]} == {"openai_compatible", "anthropic_messages", "gemini", "custom"}
    assert by_key["openai"]["region"] == "global" and by_key["openai"]["proxy_required"] is True
    assert by_key["sensenova"]["region"] == "native" and by_key["sensenova"]["proxy_required"] is False
    assert by_key["ollama"]["region"] == "local" and by_key["ollama"]["base_url"].startswith("http://127.0.0.1")
    assert by_key["sensenova"]["base_url"].endswith("/compatible-mode/v2")
    assert by_key["sensenova"]["default_headers"]["Content-Type"] == "application/json"


def test_model_capabilities_are_inferred_from_model_id(client):
    cases={
        "gpt-4o-mini":({"text","vision"},{"text"}),
        "moonshotai/Kimi-K2.5":({"text","vision","long_context"},{"text"}),
        "text-embedding-3-large":({"text"},{"embeddings"}),
        "whisper-1":({"text","audio"},{"text"}),
        "flux-1.1-pro":({"text"},{"images"}),
        "sora-2-video-generation":({"text"},{"video"}),
        "vendor/reranker-v2":({"text"},{"rerank"}),
    }
    for model_id,(expected_input,expected_output) in cases.items():
        response=client.post("/api/admin/upstream-models/infer-capabilities",json={"model_id":model_id})
        assert response.status_code==200,response.text
        assert set(response.json()["input_capabilities_json"])==expected_input
        assert set(response.json()["output_capabilities_json"])==expected_output
    metadata_response=client.post("/api/admin/upstream-models/infer-capabilities",json={"model_id":"vendor/multimodal-001","metadata":{"architecture":{"input_modalities":["text","image","audio","video"],"output_modalities":["text","image"]}}})
    assert metadata_response.status_code==200,metadata_response.text
    assert set(metadata_response.json()["input_capabilities_json"])=={"text","vision","audio","video"}
    assert set(metadata_response.json()["output_capabilities_json"])=={"text","images"}
    limits_response=client.post("/api/admin/upstream-models/infer-capabilities",json={"model_id":"vendor/catalog-model","metadata":{"limits":{"inputTokenLimit":1048576,"outputTokenLimit":65536}}})
    assert limits_response.json()["context_window"]==1048576
    assert limits_response.json()["max_output_tokens"]==65536
    assert limits_response.json()["inference_confidence"]=="high"
    gemma=client.post("/api/admin/upstream-models/infer-capabilities",json={"model_id":"google/gemma-4-31b-it"}).json()
    assert set(gemma["input_capabilities_json"])=={"text","vision","long_context"}
    assert gemma["inference_confidence"]=="medium" and gemma["requires_confirmation"] is False
    unknown=client.post("/api/admin/upstream-models/infer-capabilities",json={"model_id":"vendor/unknown-001"}).json()
    assert unknown["inference_confidence"]=="low" and unknown["requires_confirmation"] is True
    recursive=client.post("/api/admin/upstream-models/infer-capabilities",json={"model_id":"vendor/catalog-model","metadata":{"catalog":{"architecture":{"supportedInputModalities":["text","image","file"],"supportedOutputModalities":["text","function_calling"]}}}}).json()
    assert set(recursive["input_capabilities_json"])=={"text","vision","files"}
    assert set(recursive["output_capabilities_json"])=={"text","tools"}
    provider=_provider(client)
    created=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models",json={"model_id":"text-embedding-3-small"})
    assert created.status_code==201,created.text
    assert created.json()["input_capabilities_json"]==["text"]
    assert created.json()["output_capabilities_json"]==["embeddings"]

def test_same_template_creates_independent_instances_and_duplicate_names_stay_unique(client):
    first=_provider(client,name=f"same-a-{uuid4().hex}",api_key="first-placeholder")
    second=_provider(client,name=f"same-b-{uuid4().hex}",api_key="second-placeholder")
    assert first["id"]!=second["id"] and first["template_key"]==second["template_key"]=="openai"
    duplicate_one=client.post(f"/api/admin/provider-instances/{first['id']}/duplicate")
    duplicate_two=client.post(f"/api/admin/provider-instances/{first['id']}/duplicate")
    assert duplicate_one.status_code==duplicate_two.status_code==201
    assert duplicate_one.json()["name"]!=duplicate_two.json()["name"]


def test_template_host_override_keeps_required_api_path(client):
    created=_provider(
        client,
        template_key="lm_studio",
        base_url="http://192.168.8.101:1234",
        api_key="",
    )
    assert created["base_url"]=="http://192.168.8.101:1234/v1"
    updated=client.patch(
        f"/api/admin/provider-instances/{created['id']}",
        json={"template_key":"lm_studio","base_url":"http://192.168.8.102:1234"},
    )
    assert updated.status_code==200,updated.text
    assert updated.json()["base_url"]=="http://192.168.8.102:1234/v1"

    rejected=client.patch(
        f"/api/admin/provider-instances/{created['id']}",
        json={"template_key":"openai"},
    )
    assert rejected.status_code==422
    assert "不能直接更换模板" in rejected.json()["detail"]["message"]


def test_model_sync_is_idempotent_and_provider_delete_requires_empty_instance(client):
    provider=_provider(client)
    models=[{"model_id":"remote-a","display_name":"Remote A","input_capabilities_json":["text"],"output_capabilities_json":["text"]}]
    first=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models/sync",json={"models":models})
    second=client.post(f"/api/admin/provider-instances/{provider['id']}/upstream-models/sync",json={"models":models})
    assert first.json()["added"]==1
    assert second.json()["updated"]==0 and second.json()["unchanged"]==1
    blocked=client.delete(f"/api/admin/provider-instances/{provider['id']}")
    assert blocked.status_code==409
    assert blocked.json()["detail"]["details"]["references"]["upstream_models"]==1
    model_id=client.get(f"/api/admin/provider-instances/{provider['id']}/upstream-models").json()[0]["id"]
    assert client.delete(f"/api/admin/upstream-models/{model_id}").status_code==200
    assert client.delete(f"/api/admin/provider-instances/{provider['id']}").status_code==200


def test_manual_provider_supports_protocol_oauth_proxy_and_encrypted_header_flags(client):
    provider=_provider(
        client,
        template_key="manual",
        protocol_type="anthropic_messages",
        base_url="https://manual.invalid/v1",
        oauth={"client_secret":"unit-placeholder"},
        proxy_type="http",
        proxy_url="http://127.0.0.1:8888",
        custom_headers={"X-Unit":"placeholder"},
    )
    assert provider["protocol_type"]=="anthropic_messages"
    assert provider["oauth_configured"] is True
    assert provider["proxy_configured"] is True
    assert provider["custom_headers_configured"] is True
    assert "proxy_url" not in provider and "custom_headers" not in provider


def test_capability_values_are_validated_at_api_boundary(client):
    provider=_provider(client)
    invalid=client.post(
        f"/api/admin/provider-instances/{provider['id']}/upstream-models",
        json={"model_id":"bad-capability","input_capabilities_json":["text","typo"]},
    )
    assert invalid.status_code==422
    assert invalid.json()["detail"]["type"]=="validation_error"
    assert invalid.json()["detail"]["stage"]=="capability_validation"

    model=client.post(
        f"/api/admin/provider-instances/{provider['id']}/upstream-models",
        json={"model_id":"good-capability","input_capabilities_json":["text"],"output_capabilities_json":["text","tools"]},
    ).json()
    unified=client.post(
        "/api/admin/unified-models",
        json={"name":f"caps-{uuid4().hex}","required_capabilities":{"input":["text"],"output":["text"]}},
    )
    assert unified.status_code==201
    rejected=client.post(
        f"/api/admin/unified-models/{unified.json()['id']}/candidates",
        json={"upstream_model_id":model["id"],"capability_overrides":{"output":["made_up"]}},
    )
    assert rejected.status_code==422


def test_native_task_provider_does_not_fake_an_openai_model_catalog_test(client):
    provider=_provider(
        client,
        template_key="replicate",
        base_url="https://api.replicate.com/v1",
    )
    response=client.post(f"/api/admin/provider-instances/{provider['id']}/test")
    assert response.status_code==422
    assert response.json()["detail"]["type"]=="model_discovery_unsupported"
    stored=client.get(f"/api/admin/provider-instances/{provider['id']}").json()
    assert stored["verification_status"]=="unverified"
