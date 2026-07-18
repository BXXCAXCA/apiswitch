from __future__ import annotations

import re
from typing import Any, Iterable

INPUT_CAPABILITIES = (
    "text",
    "vision",
    "files",
    "audio",
    "video",
    "tool_results",
    "long_context",
)

OUTPUT_CAPABILITIES = (
    "text",
    "tools",
    "json",
    "embeddings",
    "images",
    "audio",
    "video",
    "music",
    "moderation",
    "rerank",
    "search",
)

ALL_CAPABILITIES = tuple(dict.fromkeys((*INPUT_CAPABILITIES, *OUTPUT_CAPABILITIES)))

_CONTEXT_KEYS = {
    "context_window", "context_length", "max_context_length", "max_model_len",
    "max_sequence_length", "input_token_limit", "inputtokenlimit",
}
_OUTPUT_LIMIT_KEYS = {
    "max_output_tokens", "output_token_limit", "outputtokenlimit",
    "max_completion_tokens", "max_generation_tokens",
}


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


def _find_numeric_metadata(metadata: dict[str, Any], keys: set[str]) -> int | None:
    """Find common model-limit fields in nested provider catalog payloads."""
    queue: list[Any] = [metadata]
    visited: set[int] = set()
    normalized_keys = {re.sub(r"[^a-z0-9]", "", item) for item in keys}
    while queue:
        current = queue.pop(0)
        if id(current) in visited:
            continue
        visited.add(id(current))
        if isinstance(current, dict):
            for key, value in current.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if normalized in normalized_keys:
                    parsed = _positive_int(value)
                    if parsed is not None:
                        return parsed
                if isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(current, list):
            queue.extend(item for item in current if isinstance(item, (dict, list)))
    return None


def _walk_metadata(value: Any) -> Iterable[tuple[str, Any]]:
    """Yield every nested metadata field while retaining its original key."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key), item
            yield from _walk_metadata(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_metadata(item)


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def infer_model_capabilities(model_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Infer capabilities with explicit provenance instead of presenting guesses as facts.

    Provider catalog metadata wins.  Curated model-family rules fill common gaps in
    sparse ``/models`` responses, and unknown IDs deliberately remain text-only with
    a low-confidence marker so the UI can ask the user to confirm them.
    """
    metadata = metadata if isinstance(metadata, dict) else {}
    searchable = str(model_id or "").strip().lower()
    inputs: set[str] = {"text"}
    outputs: set[str] = {"text"}
    evidence: list[str] = []
    confidence = "low"

    def contains(*patterns: str) -> bool:
        return any(re.search(pattern, searchable) for pattern in patterns)

    if contains(r"\bembedding", r"\bbge[-_/]", r"\be5[-_/]", r"jina[-_/]?embeddings"):
        outputs = {"embeddings"}; evidence.append("模型 ID 命中向量模型规则")
    elif contains(r"\brerank", r"reranker"):
        outputs = {"rerank"}; evidence.append("模型 ID 命中重排模型规则")
    elif contains(r"\bmoderat"):
        outputs = {"moderation"}; evidence.append("模型 ID 命中内容审核模型规则")
    elif contains(r"whisper", r"speech[-_ ]?to[-_ ]?text", r"transcri", r"\basr\b"):
        inputs.add("audio"); outputs = {"text"}; evidence.append("模型 ID 命中语音识别规则")
    elif contains(r"text[-_ ]?to[-_ ]?speech", r"\btts\b", r"speech[-_ ]?synthesis"):
        outputs = {"audio"}; evidence.append("模型 ID 命中语音合成规则")
    elif contains(r"dall[-_ ]?e", r"\bflux\b", r"stable[-_ ]?diffusion", r"\bsdxl\b", r"\bimagen\b", r"image[-_ ]?(gen|generation)"):
        outputs = {"images"}; evidence.append("模型 ID 命中图像生成规则")
    elif contains(r"\bsora\b", r"\bveo[-_ ]?\d", r"video[-_ ]?(gen|generation)"):
        outputs = {"video"}; evidence.append("模型 ID 命中视频生成规则")
    elif contains(r"\bmusicgen\b", r"\bsuno\b", r"music[-_ ]?(gen|generation)"):
        outputs = {"music"}; evidence.append("模型 ID 命中音乐生成规则")

    family_rules: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
        (r"(?:^|/)gemma[-_]?4(?:[-_/]|$)", ("vision", "long_context"), ()),
        (r"\bgpt[-_]?4o", ("vision",), ()),
        (r"\bgemini(?:[-_/]|$)", ("vision", "long_context"), ()),
        (r"\bclaude[-_ ]?(?:3|4)", ("vision", "long_context"), ()),
        (r"kimi[-_ ]?k2\.5", ("vision", "long_context"), ()),
        (r"\bpixtral\b|(?:^|[-_/])(?:qwen|llava)[^/]*[-_]vl(?:[-_/]|$)", ("vision",), ()),
    )
    for pattern, inferred_inputs, inferred_outputs in family_rules:
        if re.search(pattern, searchable):
            inputs.update(inferred_inputs)
            outputs.update(inferred_outputs)
            evidence.append("模型 ID 命中已知模型族规则")
            break
    if contains(r"\bvision\b", r"(?:^|[-_/])vl(?:[-_/]|$)", r"multimodal"):
        inputs.add("vision")
        evidence.append("模型 ID 包含多模态标识")

    input_aliases = {"image": "vision", "images": "vision", "image_input": "vision", "speech": "audio", "file": "files", "document": "files", "tool_result": "tool_results"}
    output_aliases = {"image": "images", "vision": "images", "embedding": "embeddings", "speech": "audio", "function_calling": "tools", "tool_calling": "tools", "structured_output": "json"}

    def collect(keys: tuple[str, ...], *, output: bool) -> set[str]:
        allowed = set(OUTPUT_CAPABILITIES if output else INPUT_CAPABILITIES)
        aliases = output_aliases if output else input_aliases
        found: set[str] = set()
        wanted = {_normalized_key(key) for key in keys}
        for key, value in _walk_metadata(metadata):
            if _normalized_key(key) not in wanted:
                continue
            values = value if isinstance(value, list) else ([value] if isinstance(value, str) else [])
            for item in values:
                if isinstance(item, dict):
                    continue
                raw = re.sub(r"[\s-]+", "_", str(item).strip().lower())
                normalized = aliases.get(raw, raw)
                if normalized in allowed:
                    found.add(normalized)
        return found

    explicit_inputs = collect(("input_capabilities", "input_modalities", "supported_input_modalities", "modalities"), output=False)
    explicit_outputs = collect(("output_capabilities", "output_modalities", "supported_output_modalities"), output=True)
    inputs.update(explicit_inputs)
    if explicit_outputs:
        outputs = explicit_outputs
    generic_features = collect(("capabilities", "supported_features", "features"), output=False)
    generic_outputs = collect(("capabilities", "supported_features", "features"), output=True)
    inputs.update(generic_features)
    outputs.update(generic_outputs)
    if explicit_inputs or explicit_outputs or generic_features or generic_outputs:
        evidence.insert(0, "远端目录显式声明模型能力")
        confidence = "high"
    elif evidence:
        confidence = "medium"
    context = _find_numeric_metadata(metadata, _CONTEXT_KEYS)
    if context is not None and context >= 32768:
        inputs.add("long_context")
        evidence.append("远端目录声明长上下文限制")
        confidence = "high"
    if not evidence:
        evidence.append("远端目录未声明能力，模型 ID 也未命中已知规则")
    return {
        "input_capabilities_json": [item for item in INPUT_CAPABILITIES if item in inputs],
        "output_capabilities_json": [item for item in OUTPUT_CAPABILITIES if item in outputs],
        "inference_confidence": confidence,
        "inference_evidence": list(dict.fromkeys(evidence)),
        "requires_confirmation": confidence == "low",
    }


def infer_model_characteristics(model_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize capabilities and hard limits advertised by a provider catalog.

    Numeric limits are only returned when the remote metadata explicitly
    advertises them; an unknown value stays ``None`` instead of becoming a
    potentially unsafe guess.
    """
    metadata = metadata if isinstance(metadata, dict) else {}
    return {
        **infer_model_capabilities(model_id, metadata),
        "context_window": _find_numeric_metadata(metadata, _CONTEXT_KEYS),
        "max_output_tokens": _find_numeric_metadata(metadata, _OUTPUT_LIMIT_KEYS),
    }


def normalize_capabilities(value: Any, *, allowed: Iterable[str] = ALL_CAPABILITIES, field: str = "capabilities") -> list[str]:
    """Validate and de-duplicate a capability array without silently accepting typos."""
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} 必须是能力字符串数组")
    allowed_values = set(allowed)
    values = list(dict.fromkeys(item.strip() for item in value if item.strip()))
    invalid = [item for item in values if item not in allowed_values]
    if invalid:
        raise ValueError(f"{field} 包含未知能力：{', '.join(invalid)}")
    return values


def normalize_capability_map(value: Any, *, field: str) -> dict[str, list[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field} 必须是对象")
    unknown = set(value) - {"input", "output"}
    if unknown:
        raise ValueError(f"{field} 包含未知字段：{', '.join(sorted(unknown))}")
    result: dict[str, list[str]] = {}
    if "input" in value:
        result["input"] = normalize_capabilities(value["input"], allowed=INPUT_CAPABILITIES, field=f"{field}.input")
    if "output" in value:
        result["output"] = normalize_capabilities(value["output"], allowed=OUTPUT_CAPABILITIES, field=f"{field}.output")
    return result


def normalize_workflow_steps(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("ordered_steps 必须为数组")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"ordered_steps[{index}] 必须是对象")
        normalized = dict(item)
        for key in ("input", "output"):
            if key in normalized and normalized[key] not in ALL_CAPABILITIES:
                raise ValueError(f"ordered_steps[{index}].{key} 包含未知能力：{normalized[key]}")
        result.append(normalized)
    return result
