"""Uygulama takvim gunleri icin yerel saat dilimi yardimcilari.

Veritabani zaman damgalari UTC olarak kalir; yalnizca 'bugun', gunluk PnL
ve rapor gun sinirlari bu saat dilimine gore hesaplanir.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_APP_TIMEZONE = "Europe/Istanbul"
TURKEY_UTC_OFFSET = timezone(timedelta(hours=3), name="TRT")
TzInfo = Union[ZoneInfo, timezone]


@lru_cache
def get_app_timezone() -> TzInfo:
    name = os.getenv("APP_TIMEZONE", DEFAULT_APP_TIMEZONE).strip() or DEFAULT_APP_TIMEZONE
    if name in {DEFAULT_APP_TIMEZONE, "Turkey", "TR", "Asia/Istanbul"}:
        try:
            return ZoneInfo(DEFAULT_APP_TIMEZONE)
        except ZoneInfoNotFoundError:
            return TURKEY_UTC_OFFSET
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return TURKEY_UTC_OFFSET


def local_now(now: datetime | None = None) -> datetime:
    """Simdi (veya verilen an) yerel saat diliminde."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(get_app_timezone())


def local_today(now: datetime | None = None) -> date:
    """Yerel saat diliminde bugunun tarihi."""
    return local_now(now).date()


def start_of_local_day(now: datetime | None = None) -> datetime:
    """Yerel gun baslangicini UTC olarak dondurur (SQL karsilastirmalari icin)."""
    local = local_now(now).replace(hour=0, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc)


def period_starts(now: datetime | None = None) -> dict[str, datetime]:
    """Gunluk / haftalik / aylik rapor baslangiclarini UTC olarak dondurur."""
    local = local_now(now)
    return {
        "daily": start_of_local_day(now),
        "weekly": (local - timedelta(days=7)).astimezone(timezone.utc),
        "monthly": (local - timedelta(days=30)).astimezone(timezone.utc),
    }
