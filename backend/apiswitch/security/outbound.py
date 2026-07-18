from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


class OutboundURLRejected(ValueError):
    pass


_METADATA_HOSTS = {
    "metadata.google.internal",
    "metadata.google.internal.",
    "metadata.azure.internal",
    "instance-data.ec2.internal",
}


def validate_outbound_url(value: str, label: str = "Base URL") -> str:
    if any(ord(character) < 32 for character in value):
        raise OutboundURLRejected(f"{label} 包含非法控制字符")
    try:parsed=urlsplit(value);_ = parsed.port
    except ValueError as exc:raise OutboundURLRejected(f"{label} 格式无效") from exc
    if parsed.scheme not in {"http","https"} or not parsed.hostname:
        raise OutboundURLRejected(f"{label} 必须使用 HTTP(S)")
    if parsed.username is not None or parsed.password is not None:
        raise OutboundURLRejected(f"{label} 不得包含内嵌凭据")
    if parsed.fragment:
        raise OutboundURLRejected(f"{label} 不得包含 fragment")
    hostname=parsed.hostname.lower()
    if hostname in _METADATA_HOSTS or hostname.endswith(".metadata.google.internal"):
        raise OutboundURLRejected(f"{label} 不允许访问云元数据地址")
    try:address=ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:address=None
    if address and (address.is_link_local or address.is_multicast or address.is_unspecified or address.is_reserved):
        raise OutboundURLRejected(f"{label} 不允许访问链路本地、保留或组播地址")
    return value.rstrip("/")
