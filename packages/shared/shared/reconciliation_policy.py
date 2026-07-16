"""Reconciliation sonrasinda SAFE_MODE kararini standartlastirir."""

from __future__ import annotations

from .reconciliation import Mismatch

# Binance'de kapanmis ama DB'de OPEN kalan hayalet pozisyonlar otomatik kapatilir;
# bunlar tek basina SAFE_MODE nedeni olmamali.
SAFE_MODE_MISMATCH_TYPES = frozenset({
    "EXTERNAL_POSITION",
    "SIDE_MISMATCH",
    "QUANTITY_MISMATCH",
    "ENTRY_PRICE_MISMATCH",
})


def critical_mismatches_for_safe_mode(mismatches: list[Mismatch]) -> list[Mismatch]:
    return [m for m in mismatches if m.mismatch_type in SAFE_MODE_MISMATCH_TYPES]
