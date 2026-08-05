from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from apiswitch.db.models import UnifiedModel
from apiswitch.routing.engine import effective_unified_capabilities


def model_catalog_metadata(db: Session, model: UnifiedModel) -> dict[str, Any]:
    """Describe the effective model contract using common client conventions.

    OpenAI's model resource does not standardize modality discovery. Clients
    consequently use several field names for the same information. Keep those
    aliases generated from one effective-capability calculation so assisted
    capabilities (for example vision-to-text) cannot diverge by client.
    """
    capabilities = effective_unified_capabilities(db, model)
    inputs = capabilities["input"]
    outputs = capabilities["output"]
    input_modalities = [
        modality
        for modality, capability in (
            ("text", "text"),
            ("image", "vision"),
            ("audio", "audio"),
            ("file", "files"),
        )
        if capability in inputs
    ]
    output_modalities = [
        modality
        for modality, capability in (
            ("text", "text"),
            ("image", "images"),
            ("audio", "audio"),
        )
        if capability in outputs
    ]

    client_capabilities = set(inputs) | set(outputs)
    supported_features = {
        capability
        for capability in client_capabilities
        if capability in {"reasoning", "tools", "tool_results"}
    }
    if "vision" in inputs:
        # Cherry Studio's model domain calls vision input image-recognition.
        client_capabilities.add("image-recognition")
        supported_features.add("image-recognition")
    if "tools" in client_capabilities:
        # OpenAI-compatible clients commonly call tool use function calling.
        client_capabilities.add("function-call")
        supported_features.add("function-call")

    modalities = {"input": input_modalities, "output": output_modalities}
    return {
        "capabilities": sorted(client_capabilities),
        "input_capabilities": inputs,
        "output_capabilities": outputs,
        "input_modalities": input_modalities,
        "output_modalities": output_modalities,
        "inputModalities": input_modalities,
        "outputModalities": output_modalities,
        "supported_input_modalities": input_modalities,
        "supported_output_modalities": output_modalities,
        "supported_features": sorted(supported_features),
        "modalities": modalities,
        "architecture": {
            "input_modalities": input_modalities,
            "output_modalities": output_modalities,
        },
    }
