import pytest

from apiswitch.security.outbound import OutboundURLRejected, validate_outbound_url


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data",
    "http://metadata.google.internal/computeMetadata/v1",
    "http://user:password@example.com/v1",
    "http://example.com/v1#secret",
])
def test_outbound_url_policy_rejects_metadata_credentials_and_fragments(url):
    with pytest.raises(OutboundURLRejected):
        validate_outbound_url(url)


def test_local_mock_servers_and_private_provider_networks_remain_supported():
    assert validate_outbound_url("http://127.0.0.1:9000/v1") == "http://127.0.0.1:9000/v1"
    assert validate_outbound_url("https://192.168.1.10/api/") == "https://192.168.1.10/api"


def test_admin_rejects_unsafe_provider_and_webdav_urls_and_protected_headers(client):
    provider = {"name": "unsafe", "template_key": "manual", "protocol_type": "openai_compatible"}
    assert client.post("/api/admin/provider-instances", json={**provider, "base_url": "http://169.254.169.254"}).status_code == 422
    assert client.post("/api/admin/provider-instances", json={**provider, "base_url": "https://example.com/v1", "custom_headers": {"Host": "other.invalid"}}).status_code == 422
    assert client.post("/api/admin/webdav/profiles", json={"name": "unsafe", "url": "http://metadata.google.internal", "backup_password": "independent"}).status_code == 422
