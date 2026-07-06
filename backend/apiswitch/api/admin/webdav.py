import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import WebDAVProfile
from apiswitch.schemas.webdav import WebDAVConnectionResult, WebDAVProfileCreate, WebDAVProfileRead, WebDAVProfileUpdate
from apiswitch.security.crypto import secret_crypto

router = APIRouter(prefix="/api/admin/webdav", tags=["Admin - WebDAV"])


def _get_profile(db: Session, profile_id: int) -> WebDAVProfile:
    profile = db.get(WebDAVProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WebDAV profile not found")
    return profile


def _to_read(profile: WebDAVProfile) -> WebDAVProfileRead:
    return WebDAVProfileRead(
        id=profile.id,
        name=profile.name,
        url=profile.url,
        username=profile.username,
        enabled=profile.enabled,
        password_configured=bool(profile.password_encrypted),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("")
async def list_webdav_profiles(db: Session = Depends(get_db)) -> list[WebDAVProfileRead]:
    profiles = db.scalars(select(WebDAVProfile).order_by(WebDAVProfile.id.desc())).all()
    return [_to_read(profile) for profile in profiles]


@router.post("")
async def create_webdav_profile(payload: WebDAVProfileCreate, db: Session = Depends(get_db)) -> WebDAVProfileRead:
    profile = WebDAVProfile(
        name=payload.name,
        url=payload.url,
        username=payload.username,
        password_encrypted=secret_crypto.encrypt(payload.password or "") if payload.password else None,
        enabled=payload.enabled,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_read(profile)


@router.patch("/{profile_id}")
async def update_webdav_profile(
    profile_id: int,
    payload: WebDAVProfileUpdate,
    db: Session = Depends(get_db),
) -> WebDAVProfileRead:
    profile = _get_profile(db, profile_id)
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        password = data.pop("password")
        profile.password_encrypted = secret_crypto.encrypt(password) if password else None
    for key, value in data.items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return _to_read(profile)


@router.delete("/{profile_id}")
async def delete_webdav_profile(profile_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    profile = _get_profile(db, profile_id)
    db.delete(profile)
    db.commit()
    return {"deleted": True}


@router.post("/{profile_id}/test")
async def test_webdav_profile(profile_id: int, db: Session = Depends(get_db)) -> WebDAVConnectionResult:
    profile = _get_profile(db, profile_id)
    if profile.url.startswith("mock://"):
        return WebDAVConnectionResult(ok=True, message="Mock WebDAV connection succeeded", status_code=200)

    password = secret_crypto.decrypt(profile.password_encrypted or "") if profile.password_encrypted else None
    auth = (profile.username, password) if profile.username and password is not None else None
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.request("PROPFIND", profile.url, auth=auth, headers={"Depth": "0"})
        ok = response.status_code in {200, 207, 301, 302, 401, 403}
        if response.status_code in {401, 403}:
            return WebDAVConnectionResult(
                ok=False,
                message="WebDAV server reached but credentials were rejected",
                status_code=response.status_code,
            )
        return WebDAVConnectionResult(
            ok=ok,
            message="WebDAV server reached" if ok else "WebDAV server returned an unexpected response",
            status_code=response.status_code,
        )
    except Exception as exc:  # noqa: BLE001
        return WebDAVConnectionResult(ok=False, message=str(exc), status_code=None)
