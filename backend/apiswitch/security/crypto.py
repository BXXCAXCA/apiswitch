from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class SecretCryptoError(ValueError):
    """Raised when encrypted configuration cannot be safely processed."""


class SecretCrypto:
    """Encrypt credentials with an operator-supplied Fernet master key.

    The key is intentionally never generated or persisted by APISwitch: an
    unattended generated key would make backups impossible to restore and can
    accidentally become another plaintext secret on disk.  Set
    ``APISWITCH_MASTER_KEY`` to a Fernet key before storing any real secret.
    """

    _PREFIX = "aps:v1:"
    _LEGACY_PREFIX = "stage1-placeholder:"

    def _fernet(self) -> Fernet:
        key = os.getenv("APISWITCH_MASTER_KEY")
        if not key:
            raise SecretCryptoError(
                "APISWITCH_MASTER_KEY must be set before storing encrypted secrets"
            )
        try:
            return Fernet(key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise SecretCryptoError(
                "APISWITCH_MASTER_KEY must be a URL-safe base64 Fernet key"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return f"{self._PREFIX}{self._fernet().encrypt(plaintext.encode('utf-8')).decode('ascii')}"

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        # Legacy values can be read so operators can rotate them, but no new
        # plaintext/placeholder value is ever written.
        if ciphertext.startswith(self._LEGACY_PREFIX):
            return ciphertext[len(self._LEGACY_PREFIX) :]
        if not ciphertext.startswith(self._PREFIX):
            raise SecretCryptoError("Unsupported encrypted secret format")
        try:
            return self._fernet().decrypt(ciphertext[len(self._PREFIX) :].encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretCryptoError("Encrypted secret cannot be decrypted with APISWITCH_MASTER_KEY") from exc

    def needs_migration(self, ciphertext: str | None) -> bool:
        return bool(ciphertext) and not ciphertext.startswith(self._PREFIX)


secret_crypto = SecretCrypto()
