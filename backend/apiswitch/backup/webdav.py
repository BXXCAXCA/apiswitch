"""Small, dependency-free WebDAV transport used for encrypted backup archives.

The transport intentionally only moves already-encrypted ``.apsbak`` files.  It
does not inspect or decrypt their contents and it never performs a restore.
"""
from __future__ import annotations

import base64
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree


class WebDAVError(RuntimeError):
    pass


def _url(base_url: str, remote_path: str) -> str:
    if not remote_path or remote_path.startswith("/") or ".." in Path(remote_path).parts:
        raise WebDAVError("远端归档路径无效")
    return base_url.rstrip("/") + "/" + quote(remote_path, safe="/-_.")


def _request(url: str, method: str, username: str | None, password: str | None, data: bytes | None = None, extra_headers: dict[str,str] | None = None) -> bytes:
    headers = {"User-Agent": "APISwitch/2", "Accept": "*/*"}
    if username:
        credential = f"{username}:{password or ''}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(credential).decode("ascii")
    if data is not None:
        headers["Content-Type"] = "application/octet-stream"
        headers["Content-Length"] = str(len(data))
    headers.update(extra_headers or {})
    try:
        with urlopen(Request(url, data=data, headers=headers, method=method), timeout=15) as response:
            return response.read()
    except HTTPError as exc:
        raise WebDAVError(f"WebDAV {method} 失败（HTTP {exc.code}）") from exc
    except URLError as exc:
        raise WebDAVError("无法连接 WebDAV 服务") from exc


def test(base_url: str, username: str | None, password: str | None) -> None:
    _request(base_url, "OPTIONS", username, password)


def list_archives(base_url: str, username: str | None, password: str | None) -> list[dict[str, str | int | None]]:
    payload=_request(base_url.rstrip("/")+"/","PROPFIND",username,password,b"",{"Depth":"1","Content-Type":"application/xml"})
    try:root=ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:raise WebDAVError("WebDAV 列表响应无效") from exc
    base_path=urlsplit(base_url).path.rstrip("/")+"/";items=[]
    for response in root.findall("{DAV:}response"):
        href=response.findtext("{DAV:}href") or "";path=unquote(urlsplit(href).path)
        if path.rstrip("/")==base_path.rstrip("/") or path.endswith("/"):continue
        remote_path=path[len(base_path):] if path.startswith(base_path) else Path(path).name
        if not remote_path.endswith(".apsbak"):continue
        length=response.findtext(".//{DAV:}getcontentlength");modified=response.findtext(".//{DAV:}getlastmodified")
        items.append({"remote_path":remote_path,"size":int(length) if length and length.isdigit() else None,"modified":modified})
    return sorted(items,key=lambda item:str(item["remote_path"]))


def upload(base_url: str, remote_path: str, username: str | None, password: str | None, source: Path) -> None:
    _request(_url(base_url, remote_path), "PUT", username, password, source.read_bytes())


def download(base_url: str, remote_path: str, username: str | None, password: str | None, destination: Path) -> None:
    payload = _request(_url(base_url, remote_path), "GET", username, password)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.write_bytes(payload)
    temporary.replace(destination)
