"""Zarar esiginde pozisyona ekleme (DCA) yardimcilari.

Ornek: -%25'te ekleme, -%50'de tamamen kapatma.
"""

from __future__ import annotations

from decimal import Decimal


def effective_stop_loss_roi_pct(
    stop_loss_roi_pct: Decimal,
    *,
    loss_add_enabled: bool,
    loss_add_max_count: int,
    loss_add_count: int,
) -> Decimal:
    """Borsadaki koruyucu SL icin efektif ROI hedefi (nihai kapanis seviyesi)."""
    _ = (loss_add_enabled, loss_add_max_count, loss_add_count)
    return stop_loss_roi_pct


def is_normal_market_position(*, is_external: bool, open_reason: str | None) -> bool:
    """Olta / harici / limit ile acilmis pozisyonlari haric tutar."""
    if is_external:
        return False
    reason = (open_reason or "").lower()
    if "limit" in reason or "olta" in reason or "external" in reason:
        return False
    return True


def should_loss_add(
    roi_pct: Decimal,
    *,
    loss_add_trigger_roi_pct: Decimal,
    stop_loss_roi_pct: Decimal,
    loss_add_enabled: bool,
    loss_add_max_count: int,
    loss_add_count: int,
    is_normal_position: bool,
) -> bool:
    if not is_normal_position or not loss_add_enabled:
        return False
    if loss_add_count >= loss_add_max_count:
        return False
    if loss_add_trigger_roi_pct >= stop_loss_roi_pct:
        return False
    return roi_pct <= -loss_add_trigger_roi_pct and roi_pct > -stop_loss_roi_pct
