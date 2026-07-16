"""Risk olaylari, bot olaylari, audit log, worker lock, sistem sagligi, reconciliation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class RiskEvent(Base, TimestampMixin):
    __tablename__ = "risk_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(16), default="WARNING", nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    bot_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)


class BotEvent(Base, TimestampMixin):
    __tablename__ = "bot_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    bot_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)


class WorkerLock(Base, TimestampMixin):
    """Redis distributed lock'un veritabani tarafindaki denetim izi."""

    __tablename__ = "worker_locks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    lock_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    holder_id: Mapped[str] = mapped_column(String(64), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SystemHealth(Base, TimestampMixin):
    __tablename__ = "system_health"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # bilesen adi: api|worker|redis|postgres|binance_ws...
    status: Mapped[str] = mapped_column(String(16), default="UNKNOWN", nullable=False)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReconciliationRun(Base, TimestampMixin):
    __tablename__ = "reconciliation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False)  # startup|manual|scheduled|reconnect
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    mismatches_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    external_positions_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    entered_safe_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramDeliveryLog(Base, TimestampMixin):
    """Musteri bazli Telegram bildirim gonderim kaydi (basari / atlama / hata)."""

    __tablename__ = "telegram_delivery_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # sent|skipped|failed
    skip_reason: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    chat_id_masked: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bot_id_masked: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="worker", nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
