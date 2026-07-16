"""Hassas veri maskeleme (sartname bolum 22 & 28).

Loglarda ve hata mesajlarinda API key, secret, sifre, token, cookie ve
Authorization header degerleri kesinlikle acik metin olarak yer almamalidir.
"""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(api[_-]?key|secret|password|passwd|token|cookie|authorization|signature)",
    re.IGNORECASE,
)

_MASK = "***REDACTED***"


def mask_value(value: str) -> str:
    if not value:
        return value
    if len(value) <= 8:
        return _MASK
    return f"{value[:4]}{_MASK}{value[-2:]}"


def mask_sensitive_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Verilen dict icindeki hassas alanlari (iceriye dogru recursive) maskeler."""

    masked: dict[str, Any] = {}
    for key, value in data.items():
        if _SENSITIVE_KEY_PATTERN.search(str(key)):
            masked[key] = _MASK
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_dict(value)
        elif isinstance(value, list):
            masked[key] = [mask_sensitive_dict(v) if isinstance(v, dict) else v for v in value]
        else:
            masked[key] = value
    return masked


def mask_text(text: str) -> str:
    """Duz metin icindeki olasi ``key=value`` / ``"key": "value"`` kaliplarini maskeler."""

    def _replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{_MASK}"

    pattern = re.compile(
        r"((?:api[_-]?key|secret|password|passwd|token|cookie|authorization|signature)"
        r"\s*[=:]\s*[\"']?)([^\s\"',}]+)",
        re.IGNORECASE,
    )
    return pattern.sub(lambda m: f"{m.group(1)}{_MASK}", text)
