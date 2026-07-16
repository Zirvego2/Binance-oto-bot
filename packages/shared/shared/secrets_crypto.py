"""Hassas profil verileri icin sifreleme (Fernet)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _derive_fernet_key(raw_key: str, fallback_secret: str) -> bytes:
    source = raw_key.strip() or fallback_secret.strip()
    if not source:
        raise ValueError("APP_ENCRYPTION_KEY veya APP_SECRET tanimli olmali")
    try:
        decoded = base64.urlsafe_b64decode(source.encode("utf-8"))
        if len(decoded) == 32:
            return base64.urlsafe_b64encode(decoded)
    except Exception:
        pass
    digest = hashlib.sha256(source.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet(encryption_key: str, app_secret: str) -> Fernet:
    return Fernet(_derive_fernet_key(encryption_key, app_secret))


def encrypt_secret(value: str, *, encryption_key: str, app_secret: str) -> str:
    if not value:
        return ""
    token = get_fernet(encryption_key, app_secret).encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(value: str | None, *, encryption_key: str, app_secret: str) -> str:
    if not value:
        return ""
    try:
        plain = get_fernet(encryption_key, app_secret).decrypt(value.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("encrypted_secret_invalid") from exc
    return plain.decode("utf-8")
