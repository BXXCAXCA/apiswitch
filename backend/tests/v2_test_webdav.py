from __future__ import annotations

from pathlib import Path
import sqlite3
from contextlib import closing

import pytest

from apiswitch.backup import webdav
from apiswitch.backup import archive as backup_archive
from apiswitch.backup.archive import BackupError, create_archive, restore_archive


class _Response:
    def __init__(self, payload: bytes = b"") -> None:
        self.payload = payload

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self) -> bytes: return self.payload


def test_webdav_transport_uses_authenticated_options_put_and_get(tmp_path: Path, monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request.get_method(), request.full_url, request.data, request.headers))
        return _Response(b"encrypted-backup")

    monkeypatch.setattr(webdav, "urlopen", fake_urlopen)
    source = tmp_path / "source.apsbak"; source.write_bytes(b"ciphertext")
    destination = tmp_path / "download.apsbak"
    webdav.test("https://dav.invalid/root", "unit", "not-a-real-password")
    webdav.upload("https://dav.invalid/root", "archives/a.apsbak", "unit", "not-a-real-password", source)
    webdav.download("https://dav.invalid/root", "archives/a.apsbak", "unit", "not-a-real-password", destination)
    assert [method for method, *_ in requests] == ["OPTIONS", "PUT", "GET"]
    assert requests[1][2] == b"ciphertext"
    assert all("Authorization" in headers for *_, headers in requests)
    assert destination.read_bytes() == b"encrypted-backup"


def test_webdav_remote_archive_listing_uses_propfind(monkeypatch):
    xml = b'''<?xml version="1.0"?>
    <d:multistatus xmlns:d="DAV:">
      <d:response><d:href>/root/</d:href></d:response>
      <d:response><d:href>/root/backup-a.apsbak</d:href><d:propstat><d:prop><d:getcontentlength>123</d:getcontentlength><d:getlastmodified>Thu, 16 Jul 2026 00:00:00 GMT</d:getlastmodified></d:prop></d:propstat></d:response>
      <d:response><d:href>/root/ignored.txt</d:href></d:response>
    </d:multistatus>'''
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return _Response(xml)

    monkeypatch.setattr(webdav, "urlopen", fake_urlopen)
    items = webdav.list_archives("https://dav.invalid/root", "unit", "password")
    assert items == [{"remote_path": "backup-a.apsbak", "size": 123, "modified": "Thu, 16 Jul 2026 00:00:00 GMT"}]
    assert requests[0].get_method() == "PROPFIND"
    assert requests[0].headers["Depth"] == "1"


def _write_database(path: Path, value: str) -> None:
    with closing(sqlite3.connect(path)) as db:
        db.execute("create table if not exists marker(value text)")
        db.execute("create table if not exists schema_metadata(generation integer)")
        if db.execute("select count(*) from schema_metadata").fetchone()[0] == 0:
            db.execute("insert into schema_metadata values (2)")
        db.execute("delete from marker")
        db.execute("insert into marker values (?)", (value,))
        db.commit()


def _read_database(path: Path) -> str:
    with closing(sqlite3.connect(path)) as db:
        return db.execute("select value from marker").fetchone()[0]


def test_encrypted_full_restore_validates_before_replacing_local_data(tmp_path: Path):
    data = tmp_path / "data"; data.mkdir()
    _write_database(data / "apiswitch.db", "archived")
    (data / "master.key").write_text("archived-key", encoding="utf-8")
    (data / "files").mkdir(); (data / "files" / "kept.txt").write_text("archived-file", encoding="utf-8")
    (data / "logs").mkdir(); (data / "logs" / "gateway.log").write_text("archived-log", encoding="utf-8")
    (data / "runtime.json").write_text('{"port":8080}', encoding="utf-8")
    encrypted = tmp_path / "full.apsbak"
    create_archive(data, "independent-backup-password", encrypted)

    _write_database(data / "apiswitch.db", "local")
    (data / "master.key").write_text("local-key", encoding="utf-8")
    (data / "files" / "extra.txt").write_text("local-extra", encoding="utf-8")
    before = {"db": _read_database(data / "apiswitch.db"), "key": (data / "master.key").read_text(encoding="utf-8")}
    with pytest.raises(BackupError, match="密码错误|归档已损坏"):
        restore_archive(data, "wrong-password", encrypted)
    assert _read_database(data / "apiswitch.db") == before["db"]
    assert (data / "master.key").read_text(encoding="utf-8") == before["key"]

    restore_archive(data, "independent-backup-password", encrypted)
    assert _read_database(data / "apiswitch.db") == "archived"
    assert (data / "master.key").read_text(encoding="utf-8") == "archived-key"
    assert (data / "files" / "kept.txt").read_text(encoding="utf-8") == "archived-file"
    assert not (data / "files" / "extra.txt").exists()
    assert (data / "runtime.json").read_text(encoding="utf-8") == '{"port":8080}'
    assert list((data / "backups").glob("pre-restore-*.db"))


def test_restore_rolls_back_when_installation_fails(tmp_path: Path, monkeypatch):
    data = tmp_path / "data"; data.mkdir()
    _write_database(data / "apiswitch.db", "archived")
    (data / "master.key").write_text("archived-key", encoding="utf-8")
    encrypted = tmp_path / "full.apsbak"
    create_archive(data, "independent-backup-password", encrypted)
    _write_database(data / "apiswitch.db", "local")
    (data / "master.key").write_text("local-key", encoding="utf-8")
    original_replace = backup_archive.os.replace

    def fail_install(source, destination):
        source_path = Path(source)
        if "-restore-" in str(source_path.parent.parent) and source_path.name == "master.key":
            raise OSError("simulated install failure")
        return original_replace(source, destination)

    monkeypatch.setattr(backup_archive.os, "replace", fail_install)
    with pytest.raises(BackupError, match="已回滚"):
        restore_archive(data, "independent-backup-password", encrypted)
    assert _read_database(data / "apiswitch.db") == "local"
    assert (data / "master.key").read_text(encoding="utf-8") == "local-key"
