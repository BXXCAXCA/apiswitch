from __future__ import annotations

from typing import Any

_OPENAI = "openai_compatible"
_TEMPLATES: list[dict[str, Any]] = [
    {"key": "openai", "name": "OpenAI", "protocol_type": "openai", "base_url": "https://api.openai.com/v1", "verification_status": "unverified", "capabilities": ["text", "vision", "tools", "embeddings", "images", "audio", "moderation"], "docs_url": "https://platform.openai.com/docs/api-reference"},
    {"key": "anthropic", "name": "Anthropic", "protocol_type": "anthropic_messages", "base_url": "https://api.anthropic.com", "verification_status": "unverified", "capabilities": ["text", "vision", "tools"], "docs_url": "https://docs.anthropic.com"},
    {"key": "gemini", "name": "Google Gemini", "protocol_type": "gemini", "base_url": "https://generativelanguage.googleapis.com", "verification_status": "unverified", "capabilities": ["text", "vision", "audio", "embeddings"], "docs_url": "https://ai.google.dev/gemini-api/docs"},
    {"key": "sensenova", "name": "SenseNova", "protocol_type": "openai_compatible", "base_url": "https://api.sensenova.cn/compatible-mode/v2", "verification_status": "unverified", "capabilities": ["text", "vision"], "docs_url": "https://www.sensecore.cn/help/docs/model-as-a-service/nova/overview/compatible-mode", "default_headers": {"Content-Type": "application/json", "Accept": "application/json"}},
    {"key": "ollama", "name": "Ollama", "protocol_type": _OPENAI, "base_url": "http://127.0.0.1:11434/v1", "verification_status": "compatible", "capabilities": ["text", "vision", "embeddings"], "docs_url": "https://docs.ollama.com/api/openai-compatibility"},
    {"key": "lm_studio", "name": "LM Studio", "protocol_type": _OPENAI, "base_url": "http://127.0.0.1:1234/v1", "verification_status": "compatible", "capabilities": ["text", "vision", "embeddings"], "docs_url": "https://lmstudio.ai/docs/developer/rest"},
    {"key": "vllm", "name": "vLLM", "protocol_type": _OPENAI, "base_url": "http://127.0.0.1:8000/v1", "verification_status": "compatible", "capabilities": ["text", "tools", "embeddings"], "docs_url": "https://docs.vllm.ai"},
    {"key": "localai", "name": "LocalAI", "protocol_type": _OPENAI, "base_url": "http://127.0.0.1:8080/v1", "verification_status": "compatible", "capabilities": ["text", "vision", "audio", "images"], "docs_url": "https://localai.io"},
    {"key": "llama_cpp", "name": "llama.cpp", "protocol_type": _OPENAI, "base_url": "http://127.0.0.1:8080/v1", "verification_status": "compatible", "capabilities": ["text", "embeddings"], "docs_url": "https://github.com/ggml-org/llama.cpp"},
]

for _key, _name, _url, _docs in [
    ("azure_openai", "Azure OpenAI", "https://YOUR-RESOURCE.openai.azure.com/openai/v1", "https://learn.microsoft.com/azure/ai-services/openai/reference"), ("groq", "Groq", "https://api.groq.com/openai/v1", "https://console.groq.com/docs/api-reference"),
    ("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "https://openrouter.ai/docs/api-reference/overview"), ("xai", "xAI", "https://api.x.ai/v1", "https://docs.x.ai/docs/api-reference"),
    ("deepseek", "DeepSeek", "https://api.deepseek.com/v1", "https://api-docs.deepseek.com"), ("fireworks", "Fireworks AI", "https://api.fireworks.ai/inference/v1", "https://docs.fireworks.ai/api-reference/introduction"),
    ("siliconflow", "SiliconFlow", "https://api.siliconflow.cn/v1", "https://docs.siliconflow.cn"), ("dashscope", "Alibaba DashScope / Qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1", "https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope"),
    ("zhipu", "Zhipu / GLM", "https://open.bigmodel.cn/api/paas/v4", "https://docs.bigmodel.cn/cn/api/introduction"), ("moonshot", "Moonshot / Kimi", "https://api.moonshot.cn/v1", "https://platform.moonshot.cn/docs/api/chat"),
    ("volcengine", "Volcengine / Doubao", "https://ark.cn-beijing.volces.com/api/v3", "https://www.volcengine.com/docs/82379/1263482"), ("minimax", "MiniMax（中国）", "https://api.minimaxi.com/v1", "https://platform.minimaxi.com/docs/api-reference/models/openai/list-models"),
    ("minimax_global", "MiniMax（国际）", "https://api.minimax.io/v1", "https://platform.minimax.io/docs/api-reference/models/openai/list-models"),
    ("qianfan", "Baidu Qianfan", "https://qianfan.baidubce.com/v2", "https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html"), ("hunyuan", "Tencent Hunyuan", "https://api.hunyuan.cloud.tencent.com/v1", "https://cloud.tencent.com/document/product/1729"),
    ("modelscope", "ModelScope 推理 API", "https://api-inference.modelscope.cn/v1", "https://modelscope.cn/learn/2558"),
    ("modelscope_local", "ModelScope 本地部署", "http://127.0.0.1:8000/v1", "https://modelscope.cn/docs"),
    ("together", "Together AI", "https://api.together.xyz/v1", "https://docs.together.ai/reference"), ("mistral", "Mistral AI", "https://api.mistral.ai/v1", "https://docs.mistral.ai/api"), ("cohere", "Cohere", "https://api.cohere.ai/compatibility/v1", "https://docs.cohere.com/docs/compatibility-api"),
    ("cerebras", "Cerebras", "https://api.cerebras.ai/v1", "https://inference-docs.cerebras.ai/api-reference"), ("sambanova", "SambaNova", "https://api.sambanova.ai/v1", "https://docs.sambanova.ai/docs/en/api-reference/overview"), ("nvidia_nim", "NVIDIA NIM", "https://integrate.api.nvidia.com/v1", "https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html"),
    ("perplexity", "Perplexity", "https://api.perplexity.ai/v1", "https://docs.perplexity.ai/docs/agent-api/openai-compatibility"), ("cloudflare_workers_ai", "Cloudflare Workers AI / AI Gateway", "https://api.cloudflare.com/client/v4/accounts/YOUR-ACCOUNT-ID/ai/v1", "https://developers.cloudflare.com/ai-gateway/usage/rest-api/"),
    ("huggingface", "Hugging Face Inference Providers", "https://router.huggingface.co/v1", "https://huggingface.co/docs/inference-providers/en/index"), ("github_models", "GitHub Models", "https://models.github.ai/inference", "https://docs.github.com/en/rest/models/catalog"),
    ("deepinfra", "DeepInfra", "https://api.deepinfra.com/v1/openai", "https://deepinfra.com/docs"), ("replicate", "Replicate", "https://api.replicate.com/v1", "https://replicate.com/docs/reference/http"), ("fal", "Fal AI", "https://fal.run", "https://docs.fal.ai/model-apis"),
    ("novita", "Novita AI", "https://api.novita.ai/openai/v1", "https://novita.ai/docs/api-reference/model-apis-llm-list-models"), ("featherless", "Featherless AI", "https://api.featherless.ai/v1", "https://featherless.ai/docs"),
    ("nscale", "Nscale", "https://inference.api.nscale.com/v1", "https://docs.nscale.com"), ("ovh", "OVHcloud AI Endpoints", "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1", "https://help.ovhcloud.com/csm/en-public-cloud-ai-endpoints"),
    ("scaleway", "Scaleway", "https://api.scaleway.ai/v1", "https://www.scaleway.com/en/docs/generative-apis/api-cli/"), ("wavespeed", "WaveSpeedAI", "https://api.wavespeed.ai/api/v3", "https://wavespeed.ai/docs"),
]:
    _TEMPLATES.append({"key": _key, "name": _name, "protocol_type": _OPENAI, "base_url": _url, "verification_status": "unverified", "capabilities": ["text"], "docs_url": _docs})

_TEMPLATES.extend([
    {"key":"vertex_ai","name":"Google Vertex AI","protocol_type":"custom","base_url":"https://REGION-aiplatform.googleapis.com/v1/projects/PROJECT-ID/locations/REGION/endpoints/openapi","verification_status":"unverified","capabilities":["text","vision","embeddings","images"],"docs_url":"https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/call-vertex-using-openai-library","auth_type":"oauth","model_list_path":"","configuration_hint":"请替换 REGION 和 PROJECT-ID；当前未内置 Google OAuth 令牌刷新适配。"},
    {"key":"bedrock","name":"AWS Bedrock","protocol_type":"custom","base_url":"https://bedrock-mantle.REGION.api.aws/v1","verification_status":"unverified","capabilities":["text","vision","embeddings","images"],"docs_url":"https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html","auth_type":"aws_credentials","model_list_path":"","configuration_hint":"请替换 REGION；当前未内置 AWS 凭据签名/短期密钥适配。"},
])

for _item in _TEMPLATES:
    if _item["key"] in {"replicate", "fal", "wavespeed"}:
        _item["protocol_type"] = "custom"
        _item["model_list_path"] = ""
        _item["configuration_hint"] = "该供应商使用原生任务协议，尚未内置可靠转换器；可手工维护模型，但不会冒充 OpenAI-Compatible。"
    elif _item["key"] == "cloudflare_workers_ai":
        _item["model_list_path"] = ""
        _item["configuration_hint"] = "请将 YOUR-ACCOUNT-ID 替换为 Cloudflare Account ID。"

_TEMPLATES.append({"key": "manual", "name": "手动供应商", "protocol_type": _OPENAI, "base_url": "", "verification_status": "manual", "capabilities": [], "docs_url": ""})

_LOCAL_KEYS = {"ollama", "lm_studio", "vllm", "localai", "llama_cpp", "modelscope_local"}
_NATIVE_KEYS = {
    "sensenova", "deepseek", "siliconflow", "dashscope", "zhipu", "moonshot",
    "volcengine", "minimax", "qianfan", "hunyuan", "modelscope",
}
_MANUAL_TEMPLATES = [
    {"key": "manual", "name": "手动供应商 · OpenAI 兼容", "protocol_type": "openai_compatible", "default_headers": {}},
    {"key": "manual_anthropic", "name": "手动供应商 · Anthropic Messages", "protocol_type": "anthropic_messages", "default_headers": {"anthropic-version": "2023-06-01"}},
    {"key": "manual_gemini", "name": "手动供应商 · Gemini", "protocol_type": "gemini", "default_headers": {}},
    {"key": "manual_custom", "name": "手动供应商 · 自定义协议", "protocol_type": "custom", "default_headers": {}},
]


def _template_region(key: str) -> str:
    if key in _LOCAL_KEYS:
        return "local"
    if key in _NATIVE_KEYS or key.startswith("manual"):
        return "native"
    return "global"


def _validate_catalog(rows: list[dict[str, Any]]) -> None:
    """Fail fast when a template ships with an invalid region or default address."""
    from urllib.parse import urlsplit

    keys: set[str] = set()
    for row in rows:
        key = str(row.get("key") or "")
        if not key or key in keys:
            raise ValueError(f"供应商模板 key 无效或重复：{key!r}")
        keys.add(key)
        if row.get("region") not in {"global", "native", "local"}:
            raise ValueError(f"供应商模板 {key} 的地区必须是 global/native/local")
        base_url = str(row.get("base_url") or "")
        if key.startswith("manual"):
            if base_url:
                raise ValueError(f"手动供应商模板 {key} 不应预填地址")
            continue
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"供应商模板 {key} 的默认地址无效")
        if row["region"] == "local" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(f"本地供应商模板 {key} 必须使用回环地址")


def list_templates() -> list[dict[str, Any]]:
    result=[]
    manual_base = next(item for item in _TEMPLATES if item["key"] == "manual")
    source = [
        {**manual_base, **manual}
        for manual in _MANUAL_TEMPLATES
    ] + [item for item in _TEMPLATES if item["key"] != "manual"]
    for item in source:
        row=dict(item)
        row.setdefault("auth_type","none" if row["key"] in _LOCAL_KEYS else "api_key")
        row.setdefault("model_list_path","/models" if row["protocol_type"] in {"openai","openai_compatible"} else "/v1/models")
        row.setdefault("default_headers",{})
        row.setdefault("region", _template_region(row["key"]))
        row["proxy_required"] = row["region"] == "global"
        row.setdefault("configuration_hint","")
        result.append(row)
    _validate_catalog(result)
    return result


def get_template(key: str) -> dict[str, Any] | None:
    return next((item for item in list_templates() if item["key"] == key), None)
