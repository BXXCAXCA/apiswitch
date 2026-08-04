import json
from types import SimpleNamespace

from apiswitch.gateway.v2 import render_egress, render_sse
from apiswitch.protocols.canonical import (
    CanonicalRequest,
    CanonicalResponse,
    response_events,
    to_openai_responses_usage,
)
from apiswitch.services import agent_configs


def _sse_records(chunks: list[str]) -> list[dict]:
    return [
        json.loads(chunk.split("data: ", 1)[1])
        for chunk in chunks
        if "data: " in chunk
    ]


def test_responses_completed_usage_is_strict_and_marks_stream_finished():
    usage = to_openai_responses_usage(
        {
            "prompt_tokens": "7",
            "completion_tokens": 3,
            "prompt_tokens_details": {
                "cached_tokens": "2",
                "provider_private_field": "must-not-leak",
            },
            "completion_tokens_details": {
                "reasoning_tokens": "1",
                "accepted_prediction_tokens": 8,
            },
        }
    )
    assert usage == {
        "input_tokens": 7,
        "input_tokens_details": {"cached_tokens": 2},
        "output_tokens": 3,
        "output_tokens_details": {"reasoning_tokens": 1},
        "total_tokens": 10,
    }

    request = CanonicalRequest(
        "chat",
        "openai_responses",
        "client-model",
        stream=True,
    )
    upstream = CanonicalResponse(text="ok", usage=usage)
    final_response = render_egress(request, upstream, "req_finish")
    records = _sse_records(
        render_sse(
            request,
            response_events(upstream, "req_finish", final_response),
        )
    )
    completed = records[-1]
    assert completed["type"] == "response.completed"
    assert completed["response"]["status"] == "completed"
    assert completed["response"]["incomplete_details"] is None
    assert completed["response"]["usage"] == usage


def test_claude_code_merge_preserves_unmanaged_settings(monkeypatch):
    models = {
        1: SimpleNamespace(id=1, name="main-model"),
        2: SimpleNamespace(id=2, name="opus-model"),
    }
    monkeypatch.setattr(
        agent_configs,
        "_model",
        lambda _db, model_id, _protocol: models[model_id],
    )
    existing = json.dumps(
        {
            "permissions": {"allow": ["Read"]},
            "hooks": {"SessionStart": [{"matcher": "*"}]},
            "env": {
                "ANTHROPIC_AUTH_TOKEN": "existing-token",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "stale-sonnet",
                "CUSTOM_ENV": "keep",
            },
        }
    )

    document = agent_configs.claude_content(
        None,
        {
            "main_model_id": 1,
            "opus_model_id": 2,
            "sonnet_model_id": None,
            "haiku_model_id": None,
        },
        "http://127.0.0.1:8080",
        existing_text=existing,
    )

    assert document["permissions"] == {"allow": ["Read"]}
    assert document["hooks"] == {"SessionStart": [{"matcher": "*"}]}
    assert document["model"] == "main-model"
    assert document["env"]["ANTHROPIC_AUTH_TOKEN"] == "existing-token"
    assert document["env"]["CUSTOM_ENV"] == "keep"
    assert document["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "opus-model"
    assert "ANTHROPIC_DEFAULT_SONNET_MODEL" not in document["env"]


def test_langcli_merge_preserves_existing_provider_and_writes_gateway(monkeypatch):
    monkeypatch.setattr(
        agent_configs,
        "_model",
        lambda _db, _model_id, _protocol: SimpleNamespace(id=3, name="lang-model"),
    )
    existing = json.dumps(
        {
            "theme": "dark",
            "env": {"KEEP": "yes"},
            "modelProviders": {
                "openai": [{"id": "existing-model", "envKey": "EXISTING_KEY"}],
            },
        }
    )

    rendered = agent_configs.agent_content(
        None,
        "langcli",
        3,
        "http://127.0.0.1:8080",
        existing_text=existing,
        api_token="ask_test_placeholder",
    )
    document = json.loads(rendered)

    assert document["theme"] == "dark"
    assert document["env"] == {
        "KEEP": "yes",
        "APISWITCH_API_KEY": "ask_test_placeholder",
    }
    assert document["model"] == "custom:lang-model"
    assert document["modelProviders"]["openai"] == [
        {"id": "existing-model", "envKey": "EXISTING_KEY"},
        {
            "id": "lang-model",
            "name": "lang-model",
            "description": "APISwitch unified model",
            "envKey": "APISWITCH_API_KEY",
            "baseUrl": "http://127.0.0.1:8080/v1",
        },
    ]
