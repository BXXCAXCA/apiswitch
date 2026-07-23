from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from contextlib import closing
from pathlib import Path
from pathlib import PurePosixPath

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from apiswitch.db.base import utc_now

MAGIC=b"APISWITCH-BACKUP-2\n"


class BackupError(ValueError): pass


def _key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(password.encode("utf-8"))


def _decrypt_archive(archive_path: Path, password: str) -> bytes:
    raw=archive_path.read_bytes()
    if not raw.startswith(MAGIC):raise BackupError("备份格式无效")
    try:
        header,cipher=raw[len(MAGIC):].split(b"\n",1);meta=json.loads(header)
        if meta.get("version")!=2:raise BackupError("备份版本不兼容")
        return AESGCM(_key(password,bytes.fromhex(meta["salt"]))).decrypt(bytes.fromhex(meta["nonce"]),cipher,None)
    except BackupError:raise
    except Exception as exc:raise BackupError("备份密码错误或归档已损坏") from exc


def inspect_archive(archive_path: Path, password: str) -> dict[str,object]:
    plain=_decrypt_archive(archive_path,password)
    try:
        with zipfile.ZipFile(io.BytesIO(plain)) as z:
            manifest=json.loads(z.read("manifest.json"))
            if manifest.get("version")!=2 or not isinstance(manifest.get("files"),list):raise BackupError("备份版本或清单无效")
            if manifest.get("schema_generation")!=2:raise BackupError("database_generation_mismatch")
            declared:set[str]=set()
            for item in manifest["files"]:
                if not isinstance(item,dict) or not isinstance(item.get("path"),str) or not isinstance(item.get("sha256"),str):raise BackupError("备份清单无效")
                relative=PurePosixPath(item["path"])
                if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] not in {"apiswitch.db","master.key","files","logs"}:raise BackupError("备份包含非法路径")
                normalized=relative.as_posix()
                if normalized in declared:raise BackupError("备份包含重复路径")
                declared.add(normalized)
                if hashlib.sha256(z.read(normalized)).hexdigest()!=item["sha256"]:raise BackupError("备份校验失败")
            archived={name for name in z.namelist() if name!="manifest.json" and not name.endswith("/")}
            if archived!=declared:raise BackupError("备份包含未声明文件")
            return {"version":2,"created_at":manifest.get("created_at"),"schema_generation":manifest.get("schema_generation"),"files":manifest["files"],"sha256":hashlib.sha256(archive_path.read_bytes()).hexdigest()}
    except BackupError:raise
    except Exception as exc:raise BackupError("备份归档无效") from exc


def create_archive(data_dir: Path, password: str, destination: Path) -> dict[str,str]:
    if not password: raise BackupError("备份密码不能为空")
    with tempfile.TemporaryDirectory() as temp:
        snapshot=Path(temp)/"snapshot"; snapshot.mkdir()
        db=data_dir/"apiswitch.db"
        if db.exists():
            with closing(sqlite3.connect(db)) as source, closing(sqlite3.connect(snapshot/"apiswitch.db")) as target:
                source.backup(target)
        manifest=[]
        for relative in ("master.key","files","logs"):
            source=data_dir/relative
            if source.is_file():
                target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            elif source.is_dir():
                for file in source.rglob("*"):
                    if file.is_file():
                        target=snapshot/file.relative_to(data_dir);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(file.read_bytes())
        for file in snapshot.rglob("*"):
            if file.is_file(): manifest.append({"path":str(file.relative_to(snapshot)).replace("\\","/"),"sha256":hashlib.sha256(file.read_bytes()).hexdigest()})
        raw=Path(temp)/"archive.zip";schema_generation=None;snapshot_db=snapshot/"apiswitch.db"
        if snapshot_db.exists():
            try:
                with closing(sqlite3.connect(snapshot_db)) as connection:
                    row=connection.execute("select generation from schema_metadata order by generation desc limit 1").fetchone();schema_generation=row[0] if row else None
            except sqlite3.Error:pass
        with zipfile.ZipFile(raw,"w",zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json",json.dumps({"version":2,"created_at":utc_now().isoformat(),"schema_generation":schema_generation,"files":manifest}))
            for file in snapshot.rglob("*"):
                if file.is_file():archive.write(file,file.relative_to(snapshot))
        salt=os.urandom(16);nonce=os.urandom(12);cipher=AESGCM(_key(password,salt)).encrypt(nonce,raw.read_bytes(),None)
        header=json.dumps({"version":2,"salt":salt.hex(),"nonce":nonce.hex()}).encode()+b"\n"
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(MAGIC+header+cipher)
    return {"path":str(destination),"sha256":hashlib.sha256(destination.read_bytes()).hexdigest()}


def restore_archive(data_dir: Path, password: str, archive_path: Path) -> None:
    plain=_decrypt_archive(archive_path,password)
    data_dir=data_dir.resolve();data_dir.mkdir(parents=True,exist_ok=True)
    transaction_id=uuid.uuid4().hex
    staging=data_dir.parent/f".{data_dir.name}-restore-{transaction_id}"
    rollback=data_dir.parent/f".{data_dir.name}-rollback-{transaction_id}"
    managed=("apiswitch.db","master.key","files","logs")
    try:
        staging.mkdir();rollback.mkdir()
        archive=staging/"payload.zip";archive.write_bytes(plain)
        with zipfile.ZipFile(archive) as z:
            try:manifest=json.loads(z.read("manifest.json"))
            except Exception as exc:raise BackupError("备份清单无效") from exc
            if manifest.get("version")!=2 or not isinstance(manifest.get("files"),list):raise BackupError("备份版本或清单无效")
            if manifest.get("schema_generation")!=2:raise BackupError("database_generation_mismatch")
            declared:set[str]=set()
            extracted=staging/"content";extracted.mkdir()
            for item in manifest["files"]:
                if not isinstance(item,dict) or not isinstance(item.get("path"),str) or not isinstance(item.get("sha256"),str):raise BackupError("备份清单无效")
                relative=PurePosixPath(item["path"])
                if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] not in managed:raise BackupError("备份包含非法路径")
                normalized=relative.as_posix()
                if normalized in declared:raise BackupError("备份包含重复路径")
                declared.add(normalized)
                try:content=z.read(normalized)
                except KeyError as exc:raise BackupError("备份缺少清单文件") from exc
                if hashlib.sha256(content).hexdigest()!=item["sha256"]:raise BackupError("备份校验失败")
                target=extracted.joinpath(*relative.parts);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
            archived={name for name in z.namelist() if name!="manifest.json" and not name.endswith("/")}
            if archived!=declared:raise BackupError("备份包含未声明文件")
        restored_db=extracted/"apiswitch.db"
        if not restored_db.is_file():raise BackupError("备份缺少数据库")
        try:
            with closing(sqlite3.connect(f"file:{restored_db.as_posix()}?mode=ro",uri=True)) as db:
                if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":raise BackupError("备份数据库校验失败")
        except BackupError:raise
        except sqlite3.Error as exc:raise BackupError("备份数据库无效") from exc

        moved_current:list[str]=[];installed:list[str]=[]
        try:
            for name in managed:
                current=data_dir/name
                if current.exists():os.replace(current,rollback/name);moved_current.append(name)
            for name in managed:
                incoming=extracted/name
                if incoming.exists():os.replace(incoming,data_dir/name);installed.append(name)
        except Exception as exc:
            for name in reversed(installed):
                current=data_dir/name
                if current.is_dir():shutil.rmtree(current,ignore_errors=True)
                else:current.unlink(missing_ok=True)
            for name in reversed(moved_current):
                saved=rollback/name
                if saved.exists():os.replace(saved,data_dir/name)
            raise BackupError("恢复写入失败，本地数据已回滚") from exc

        previous_db=rollback/"apiswitch.db"
        if previous_db.exists():
            backup=data_dir/"backups"/f"pre-restore-{utc_now().strftime('%Y%m%dT%H%M%S%fZ')}.db"
            backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous_db,backup)
    finally:
        shutil.rmtree(staging,ignore_errors=True)
        shutil.rmtree(rollback,ignore_errors=True)
