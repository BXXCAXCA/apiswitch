def test_system_upload_limit_is_enforced_by_gateway_file_endpoint(client):
    token=client.post("/api/admin/tokens",json={"name":"file-limit"}).json()["token"]
    headers={"Authorization":f"Bearer {token}"}
    client.patch("/api/admin/settings",json={"upload_limit_bytes":3})
    rejected=client.post("/v1/files",headers=headers,files={"file":("too-large.txt",b"1234","text/plain")})
    assert rejected.status_code==413
    accepted=client.post("/v1/files",headers=headers,files={"file":("ok.txt",b"123","text/plain")})
    assert accepted.status_code==200


def test_file_list_content_delete_and_token_isolation(client):
    first=client.post("/api/admin/tokens",json={"name":"file-owner"}).json()["token"]
    second=client.post("/api/admin/tokens",json={"name":"file-stranger"}).json()["token"]
    owner={"Authorization":f"Bearer {first}"}
    stranger={"Authorization":f"Bearer {second}"}
    created=client.post(
        "/v1/files",
        headers=owner,
        files={"file":("result.jsonl",b'{"ok":true}\n',"application/jsonl")},
        data={"purpose":"batch"},
    ).json()

    listing=client.get("/v1/files",headers=owner)
    assert listing.status_code==200
    assert [item["id"] for item in listing.json()["data"]]==[created["id"]]
    content=client.get(f"/v1/files/{created['id']}/content",headers=owner)
    assert content.status_code==200 and content.content==b'{"ok":true}\n'
    assert content.headers["content-type"].startswith("application/jsonl")

    assert client.get(f"/v1/files/{created['id']}",headers=stranger).status_code==404
    assert client.get(f"/v1/files/{created['id']}/content",headers=stranger).status_code==404
    assert client.delete(f"/v1/files/{created['id']}",headers=stranger).status_code==404
    deleted=client.delete(f"/v1/files/{created['id']}",headers=owner)
    assert deleted.json()=={"id":created["id"],"object":"file","deleted":True}
    assert client.get(f"/v1/files/{created['id']}",headers=owner).status_code==404
