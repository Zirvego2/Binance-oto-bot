"""Sifreleme, oturum token'i ve CSRF yardimcilari (sartname bolum 22 & 28)."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_TOKEN_BYTES = 32
CSRF_TOKEN_BYTES = 32


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _pwd_context.verify(plain_password, password_hash)
    except ValueError:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Oturum token'i veritabaninda asla duz metin saklanmaz; SHA-256 hash'i saklanir."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
