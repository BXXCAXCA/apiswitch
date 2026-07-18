"""Google OAuth authorization-code flow with PKCE for Gemini connections."""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from apiswitch.db.models import ProviderConnection
from apiswitch.security.crypto import secret_crypto

GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


class GoogleOAuthError(ValueError):
    pass


def build_google_authorization_url(
    *, client_id: str, redirect_uri: str, scopes: list[str], state: str, code_verifier: str
) -> str:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{query}"


def create_google_oauth_metadata(
    *, client_id: str, project_id: str, client_secret: str | None, redirect_uri: str, scopes: list[str]
) -> tuple[dict[str, Any], str]:
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    metadata: dict[str, Any] = {
        "oauth_provider": "google",
        "oauth_state": state,
        "oauth_code_verifier_encrypted": secret_crypto.encrypt(verifier),
        "oauth_client_id": client_id,
        "oauth_project_id": project_id,
        "oauth_redirect_uri": redirect_uri,
        "oauth_scopes": scopes,
        "oauth_pending": True,
    }
    if client_secret:
        metadata["oauth_client_secret_encrypted"] = secret_crypto.encrypt(client_secret)
    return metadata, verifier


async def exchange_google_authorization_code(connection: ProviderConnection, code: str) -> None:
    metadata = dict(connection.metadata_json or {})
    if metadata.get("oauth_provider") != "google" or not metadata.get("oauth_pending"):
        raise GoogleOAuthError("Google OAuth authorization is not pending for this connection")
    try:
        verifier = secret_crypto.decrypt(str(metadata["oauth_code_verifier_encrypted"]))
        client_secret_value = metadata.get("oauth_client_secret_encrypted")
        client_secret = secret_crypto.decrypt(str(client_secret_value)) if client_secret_value else None
        client_id = str(metadata["oauth_client_id"])
        redirect_uri = str(metadata["oauth_redirect_uri"])
    except (KeyError, ValueError) as exc:
        raise GoogleOAuthError("Google OAuth connection metadata is incomplete") from exc

    data: dict[str, str] = {
        "code": code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)
    except Exception as exc:  # noqa: BLE001
        raise GoogleOAuthError(f"Google token exchange failed: {exc}") from exc
    if response.status_code >= 400:
        raise GoogleOAuthError(f"Google token exchange failed: {response.status_code} {response.text}")
    try:
        token = response.json()
        access_token = str(token["access_token"])
    except (KeyError, ValueError, TypeError) as exc:
        raise GoogleOAuthError("Google token exchange returned no access token") from exc

    refresh_token = token.get("refresh_token")
    expires_in = token.get("expires_in")
    connection.credential_encrypted = secret_crypto.encrypt(access_token)
    if isinstance(refresh_token, str) and refresh_token:
        connection.refresh_token_encrypted = secret_crypto.encrypt(refresh_token)
    connection.expires_at = (
        datetime.utcnow() + timedelta(seconds=int(expires_in)) if isinstance(expires_in, (int, float)) else None
    )
    for key in ("oauth_state", "oauth_code_verifier_encrypted", "oauth_pending"):
        metadata.pop(key, None)
    metadata["oauth_provider"] = "google"
    metadata["oauth_scopes"] = metadata.get("oauth_scopes", [])
    connection.metadata_json = metadata
