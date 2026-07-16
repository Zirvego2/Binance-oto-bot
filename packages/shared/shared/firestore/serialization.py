"""SQL / Python degerlerini Firestore uyumlu formata cevirir."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.orm import DeclarativeBase


def serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(v) for v in value]
    return str(value)


def serialize_model_row(row: DeclarativeBase) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for column in row.__table__.columns:  # type: ignore[attr-defined]
        payload[column.name] = serialize_value(getattr(row, column.name))
    return payload


def coerce_decimal_fields(payload: dict[str, Any], decimal_keys: frozenset[str]) -> dict[str, Any]:
    out = dict(payload)
    for key in decimal_keys:
        if key in out and out[key] is not None and not isinstance(out[key], Decimal):
            out[key] = Decimal(str(out[key]))
    return out
