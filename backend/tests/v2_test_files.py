def test_system_upload_limit_is_enforced_by_gateway_file_endpoint(client):
    token=client.post("/api/admin/tokens",json={"name":"file-limit"}).json()["token"]
    headers={"Authorization":f"Bearer {token}"}
    client.patch("/api/admin/settings",json={"upload_limit_bytes":3})
    rejected=client.post("/v1/files",headers=headers,files={"file":("too-large.txt",b"1234","text/plain")})
    assert rejected.status_code==413
    accepted=client.post("/v1/files",headers=headers,files={"file":("ok.txt",b"123","text/plain")})
    assert accepted.status_code==200
