import hashlib
import secrets

TOKEN_PREFIX = "ask_"
TOKEN_RANDOM_BYTES = 32


def generate_api_token() -> str:
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(TOKEN_RANDOM_BYTES)}"


def hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_prefix(token: str) -> str:
    return token[:12]
