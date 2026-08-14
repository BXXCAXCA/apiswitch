from uuid import uuid4

from fastapi.testclient import TestClient


def _upstream_models(client: TestClient, count: int = 3) -> list[int]:
    provider = client.post(
        "/api/admin/provider-instances",
        json={
            "name": f"priority-{uuid4().hex}",
            "template_key": "openai",
            "base_url": "mock://priority",
            "api_key": "unit-only-not-a-real-key",
        },
    ).json()
    return [
        client.post(
            f"/api/admin/provider-instances/{provider['id']}/upstream-models",
            json={"model_id": f"priority-model-{index}"},
        ).json()["id"]
        for index in range(count)
    ]


def test_candidate_priority_can_be_reordered_atomically(client: TestClient):
    upstream_ids = _upstream_models(client)
    unified = client.post("/api/admin/unified-models", json={"name": "drag-candidates"}).json()
    candidates = [
        client.post(
            f"/api/admin/unified-models/{unified['id']}/candidates",
            json={"upstream_model_id": upstream_id},
        ).json()
        for upstream_id in upstream_ids
    ]
    assert [candidate["priority"] for candidate in candidates] == [1, 2, 3]

    ordered_ids = [candidates[2]["id"], candidates[0]["id"], candidates[1]["id"]]
    response = client.patch(
        f"/api/admin/unified-models/{unified['id']}/candidates/reorder",
        json={"ids": ordered_ids},
    )
    assert response.status_code == 200, response.text
    assert [candidate["id"] for candidate in response.json()] == ordered_ids
    assert [candidate["priority"] for candidate in response.json()] == [1, 2, 3]

    invalid = client.patch(
        f"/api/admin/unified-models/{unified['id']}/candidates/reorder",
        json={"ids": ordered_ids[:2]},
    )
    assert invalid.status_code == 422
    persisted = client.get(f"/api/admin/unified-models/{unified['id']}").json()["candidates"]
    assert [candidate["id"] for candidate in persisted] == ordered_ids


def test_auxiliary_models_and_workflows_support_drag_order(client: TestClient):
    upstream_ids = _upstream_models(client)
    models = [
        client.post(
            "/api/admin/auxiliary/models",
            json={"upstream_model_id": upstream_id, "capabilities": ["text"]},
        ).json()
        for upstream_id in upstream_ids
    ]
    assert [model["priority"] for model in models] == [1, 2, 3]
    model_order = [models[1]["id"], models[2]["id"], models[0]["id"]]
    reordered_models = client.patch("/api/admin/auxiliary/models/reorder", json={"ids": model_order})
    assert reordered_models.status_code == 200, reordered_models.text
    assert [model["id"] for model in reordered_models.json()] == model_order

    workflows = [
        client.post(
            "/api/admin/auxiliary/workflows",
            json={
                "workflow_type": workflow_type,
                "input_capability": "text",
                "output_capability": "text",
                "ordered_steps": [{"input": "text", "output": "text"}],
            },
        ).json()
        for workflow_type in ("context_compress", "tool_plan", "structured_repair")
    ]
    assert [workflow["priority"] for workflow in workflows] == [1, 2, 3]
    workflow_order = [workflows[2]["id"], workflows[0]["id"], workflows[1]["id"]]
    reordered_workflows = client.patch("/api/admin/auxiliary/workflows/reorder", json={"ids": workflow_order})
    assert reordered_workflows.status_code == 200, reordered_workflows.text
    assert [workflow["id"] for workflow in reordered_workflows.json()] == workflow_order
    assert [workflow["id"] for workflow in client.get("/api/admin/auxiliary/workflows").json()] == workflow_order
