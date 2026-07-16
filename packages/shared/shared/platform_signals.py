"""Platform geneli ortak sinyal ve analiz kayitlari (admin_id = NULL)."""

from __future__ import annotations

from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute

# Tum musteriler ayni analiz/sinyal havuzunu gorur.
PLATFORM_SHARED_ADMIN_ID: None = None


def is_shared_signal_row(admin_id: str | None) -> bool:
    return admin_id is None


def shared_admin_id_clause(column: InstrumentedAttribute[str | None]) -> ColumnElement[bool]:
    return column.is_(None)
