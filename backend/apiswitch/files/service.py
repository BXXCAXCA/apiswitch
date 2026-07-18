"""Local-first file storage and safe text-context extraction."""

import hashlib
import mimetypes
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.config import settings
from apiswitch.db.models import StoredFile
from apiswitch.schemas.gateway import ChatCompletionRequest, ChatMessage

_TEXT_SUFFIXES = {".txt", ".md", ".py", ".ts", ".js", ".json", ".csv", ".html", ".xml", ".yaml", ".yml"}
_MAX_CONTEXT_CHARS_PER_FILE = 24_000


def _storage_root() -> Path:
    root = Path(settings.file_storage_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_storage_path(value: str) -> Path:
    root = _storage_root()
    path = Path(value).resolve()
    if root != path and root not in path.parents:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid stored file path")
    return path


def _readable_text(file: StoredFile) -> str | None:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _TEXT_SUFFIXES and not (file.mime_type or "").startswith("text/"):
        return None
    try:
        return _safe_storage_path(file.storage_path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file is unavailable") from exc


def _owned_file(db: Session, file_id: str, api_token_id: int) -> StoredFile:
    item = db.get(StoredFile, file_id)
    if item is None or item.api_token_id != api_token_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return item


async def store_file(db: Session, upload: UploadFile, *, purpose: str, api_token_id: int) -> StoredFile:
    filename = Path(upload.filename or "upload").name
    if filename in {"", ".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file name")
    content = await upload.read(settings.file_max_upload_bytes + 1)
    if len(content) > settings.file_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.file_max_upload_bytes} byte limit",
        )
    file_id = f"file_{uuid.uuid4().hex}"
    path = _storage_root() / file_id
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail="Unable to store file") from exc
    item = StoredFile(
        id=file_id,
        api_token_id=api_token_id,
        filename=filename,
        purpose=purpose,
        mime_type=upload.content_type or mimetypes.guess_type(filename)[0],
        byte_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_path=str(path),
        status="processed",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_files(db: Session, api_token_id: int) -> list[StoredFile]:
    return db.scalars(
        select(StoredFile)
        .where(StoredFile.api_token_id == api_token_id)
        .order_by(StoredFile.created_at.desc())
    ).all()


def delete_file(db: Session, file_id: str, api_token_id: int) -> StoredFile:
    item = _owned_file(db, file_id, api_token_id)
    _safe_storage_path(item.storage_path).unlink(missing_ok=True)
    db.delete(item)
    db.commit()
    return item


def get_file_content(db: Session, file_id: str, api_token_id: int) -> tuple[StoredFile, Path]:
    item = _owned_file(db, file_id, api_token_id)
    path = _safe_storage_path(item.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file is unavailable")
    return item, path


def augment_chat_with_files(
    db: Session, request: ChatCompletionRequest, *, api_token_id: int
) -> ChatCompletionRequest:
    if not request.file_ids:
        return request
    contexts: list[str] = []
    for file_id in request.file_ids:
        item = _owned_file(db, file_id, api_token_id)
        text = _readable_text(item)
        if text is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"type": "not_supported_by_candidate", "message": f"File is not text-readable: {item.filename}"},
            )
        contexts.append(f"--- {item.filename} ---\n{text[:_MAX_CONTEXT_CHARS_PER_FILE]}")
    context_message = ChatMessage(
        role="system",
        content="User-provided file context:\n" + "\n\n".join(contexts),
    )
    return request.model_copy(update={"messages": [context_message, *request.messages]})
