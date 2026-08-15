from uuid import uuid4

from fastapi.testclient import TestClient


def _models(client: TestClient, count: int = 4):
    provider=client.post("/api/admin/provider-instances",json={"name":f"bulk-{uuid4().hex}","template_key":"openai","base_url":"mock://bulk"}).json()
    return [
        client.post(
            f"/api/admin/provider-instances/{provider['id']}/upstream-models",
            json={"model_id":f"bulk-model-{index}","input_capabilities_json":["text"],"output_capabilities_json":["text"]},
        ).json()
        for index in range(count)
    ]


def test_upstream_models_can_be_configured_in_one_atomic_bulk_operation(client: TestClient):
    models=[_models(client,1)[0],_models(client,1)[0]]
    configuration={
        "input_capabilities_json":["text","vision"],
        "output_capabilities_json":["text","tools"],
        "context_window":128000,
        "max_output_tokens":8192,
        "input_price":1.25,
        "output_price":2.5,
        "cached_input_price":0.25,
        "tags_json":["agent","vision"],
    }
    response=client.post("/api/admin/upstream-models/bulk",json={"ids":[item["id"] for item in models],"action":"configure","configuration":configuration})
    assert response.status_code==200,response.text
    assert response.json()=={"updated":2,"action":"configure"}
    listed=client.get("/api/admin/upstream-models")
    assert listed.status_code==200
    listed_by_id={item["id"]:item for item in listed.json()}
    assert {listed_by_id[item["id"]]["provider_name"] for item in models}=={
        client.get(f"/api/admin/provider-instances/{item['provider_instance_id']}").json()["name"] for item in models
    }
    for item in models:
        updated=client.patch(f"/api/admin/upstream-models/{item['id']}",json={}).json()
        for key,value in configuration.items():assert updated[key]==value
        assert updated["pricing_source"]=="manual"

    invalid=client.post("/api/admin/upstream-models/bulk",json={"ids":[models[0]["id"],99999999],"action":"configure","configuration":{"context_window":4096}})
    assert invalid.status_code==422
    assert client.patch(f"/api/admin/upstream-models/{models[0]['id']}",json={}).json()["context_window"]==128000


def test_unified_model_candidates_support_atomic_bulk_add(client: TestClient):
    models=_models(client,4)
    unified=client.post("/api/admin/unified-models",json={"name":f"bulk-unified-{uuid4().hex}"}).json()
    first=client.post(f"/api/admin/unified-models/{unified['id']}/candidates",json={"upstream_model_id":models[0]["id"]}).json()
    response=client.post(f"/api/admin/unified-models/{unified['id']}/candidates/bulk",json={"upstream_model_ids":[models[1]["id"],models[2]["id"]],"weight":80,"capability_overrides":{"output":["text","tools"]}})
    assert response.status_code==201,response.text
    added=response.json()
    assert [item["priority"] for item in added]==[2,3]
    assert all(item["weight"]==80 for item in added)
    assert all(item["capability_overrides"]=={"output":["text","tools"]} for item in added)

    duplicate=client.post(f"/api/admin/unified-models/{unified['id']}/candidates/bulk",json={"upstream_model_ids":[models[2]["id"],models[3]["id"]]})
    assert duplicate.status_code==422
    persisted=client.get(f"/api/admin/unified-models/{unified['id']}").json()["candidates"]
    assert [item["id"] for item in persisted]==[first["id"],added[0]["id"],added[1]["id"]]
    assert models[3]["id"] not in {item["upstream_model_id"] for item in persisted}
