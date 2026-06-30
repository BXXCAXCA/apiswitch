import hashlib


def embedding_cache_key(provider: str, model: str, normalized_input: str) -> str:
    raw = f"{provider}:{model}:{normalized_input}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
