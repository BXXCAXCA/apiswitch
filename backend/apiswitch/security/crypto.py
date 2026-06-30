from __future__ import annotations


class SecretCrypto:
    """Placeholder encryption boundary.

    Stage 1 keeps the interface stable. Later stages will back this with
    Windows DPAPI / Credential Manager or APISWITCH_MASTER_KEY.
    """

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return f"stage1-placeholder:{plaintext}"

    def decrypt(self, ciphertext: str) -> str:
        prefix = "stage1-placeholder:"
        if ciphertext.startswith(prefix):
            return ciphertext[len(prefix) :]
        return ciphertext


secret_crypto = SecretCrypto()
