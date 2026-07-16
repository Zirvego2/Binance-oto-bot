"""Benzersiz client order ID / algo ID / signal ID uretimi (sartname bolum 14).

Binance ``newClientOrderId`` alani en fazla 36 karakter kabul eder, bu
nedenle uretilen ID'ler bu sinira uygun ve URL-safe karakterlerden olusur.
"""

from __future__ import annotations

import secrets
import time
import uuid

_MAX_BINANCE_CLIENT_ID_LEN = 36


def _short_uuid() -> str:
    return uuid.uuid4().hex[:12]


def generate_client_order_id(prefix: str = "bot") -> str:
    """Normal (MARKET/reduce-only) emirler icin benzersiz client order ID."""

    ts = int(time.time() * 1000)
    candidate = f"{prefix}_{ts}_{_short_uuid()}"
    return candidate[:_MAX_BINANCE_CLIENT_ID_LEN]


def generate_client_algo_id(purpose: str) -> str:
    """Koruyucu (STOP_MARKET / TAKE_PROFIT_MARKET) emirler icin benzersiz ID.

    purpose: "sl" | "tp" | "trl"
    """

    ts = int(time.time() * 1000)
    candidate = f"algo_{purpose}_{ts}_{_short_uuid()}"
    return candidate[:_MAX_BINANCE_CLIENT_ID_LEN]


def generate_signal_id() -> str:
    """Her analiz/sinyal icin benzersiz ID (UUID4, cakisma olasiligi ihmal edilebilir)."""

    return str(uuid.uuid4())


def generate_idempotency_token() -> str:
    """Genel amacli, kriptografik olarak guclu rastgele idempotency token."""

    return secrets.token_urlsafe(24)
