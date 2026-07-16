"""Musteri uyelik paketleri ve sure kontrolu."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from shared.enums import UserRole

LEGACY_EXISTING_CUSTOMER_DAYS = 5 * 365
DEFAULT_APPROVAL_PLAN_ID = "6m"
MEMBERSHIP_EXPIRED_MESSAGE = (
    "Uyelik suresi doldu. Hesabinizi yenilemek icin yonetici ile iletisime gecin."
)


class MembershipPlan(TypedDict):
    id: str
    label: str
    duration_days: int
    price_usdt: int


MEMBERSHIP_PLANS: dict[str, MembershipPlan] = {
    "1m": {"id": "1m", "label": "1 Ay", "duration_days": 30, "price_usdt": 25},
    "6m": {"id": "6m", "label": "6 Ay", "duration_days": 180, "price_usdt": 100},
    "12m": {"id": "12m", "label": "12 Ay", "duration_days": 365, "price_usdt": 180},
    "legacy_5y": {
        "id": "legacy_5y",
        "label": "Mevcut Musteri (5 Yil)",
        "duration_days": LEGACY_EXISTING_CUSTOMER_DAYS,
        "price_usdt": 0,
    },
}


def list_membership_plans(*, include_legacy: bool = False) -> list[MembershipPlan]:
    plans = [MEMBERSHIP_PLANS[plan_id] for plan_id in ("1m", "6m", "12m")]
    if include_legacy:
        plans.append(MEMBERSHIP_PLANS["legacy_5y"])
    return plans


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_membership_active(admin: Any, *, now: datetime | None = None) -> bool:
    if getattr(admin, "role", None) == UserRole.PLATFORM_ADMIN.value:
        return True
    expires_at = getattr(admin, "membership_expires_at", None)
    if expires_at is None:
        return True
    current = now or datetime.now(timezone.utc)
    return _ensure_utc(expires_at) > current


def membership_days_remaining(admin: Any, *, now: datetime | None = None) -> int | None:
    expires_at = getattr(admin, "membership_expires_at", None)
    if expires_at is None:
        return None
    current = now or datetime.now(timezone.utc)
    delta = _ensure_utc(expires_at) - current
    return max(0, delta.days)


def resolve_duration_days(plan_id: str | None, duration_days: int | None) -> tuple[str, int]:
    if plan_id and plan_id in MEMBERSHIP_PLANS:
        return plan_id, MEMBERSHIP_PLANS[plan_id]["duration_days"]
    if duration_days is not None and duration_days > 0:
        return "custom", duration_days
    default = MEMBERSHIP_PLANS[DEFAULT_APPROVAL_PLAN_ID]
    return DEFAULT_APPROVAL_PLAN_ID, default["duration_days"]


def grant_membership(
    admin: Any,
    *,
    plan_id: str | None = None,
    duration_days: int | None = None,
    starts_at: datetime | None = None,
) -> datetime:
    """Yeni uyelik baslatir (onay aninda)."""
    now = starts_at or datetime.now(timezone.utc)
    resolved_plan, days = resolve_duration_days(plan_id, duration_days)
    admin.membership_plan = resolved_plan
    admin.membership_starts_at = now
    admin.membership_expires_at = now + timedelta(days=days)
    return admin.membership_expires_at


def extend_membership(
    admin: Any,
    *,
    plan_id: str | None = None,
    duration_days: int | None = None,
) -> datetime:
    """Aktif uyelige ekler; suresi dolmussa bugunden baslatir."""
    now = datetime.now(timezone.utc)
    resolved_plan, days = resolve_duration_days(plan_id, duration_days)
    current_expires = getattr(admin, "membership_expires_at", None)
    if current_expires is not None:
        current_expires = _ensure_utc(current_expires)
    if current_expires and current_expires > now:
        new_expires = current_expires + timedelta(days=days)
    else:
        new_expires = now + timedelta(days=days)
        admin.membership_starts_at = now
    admin.membership_expires_at = new_expires
    admin.membership_plan = resolved_plan
    return new_expires
