def test_batch_rejects_missing_invalid_and_foreign_input_files(client):
    first=client.post("/api/admin/tokens",json={"name":"batch-one"}).json()["token"]
    second=client.post("/api/admin/tokens",json={"name":"batch-two"}).json()["token"]
    first_headers={"Authorization":f"Bearer {first}"};second_headers={"Authorization":f"Bearer {second}"}
    assert client.post("/v1/batches",headers=first_headers,json={"input_file_id":"missing"}).status_code==400
    invalid=client.post("/v1/files",headers=first_headers,files={"file":("bad.jsonl",b"not-json","application/jsonl")}).json()
    assert client.post("/v1/batches",headers=first_headers,json={"input_file_id":invalid["id"]}).status_code==400
    assert client.post("/v1/batches",headers=second_headers,json={"input_file_id":invalid["id"]}).status_code==400
