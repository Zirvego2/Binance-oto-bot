from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class BotEventOut(BaseModel):
    id: str
    event_type: str
    message: str
    details: dict[str, Any] | None
    bot_mode: str | None
    admin_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class RiskEventOut(BaseModel):
    id: str
    event_type: str
    symbol: str | None
    severity: str
    message: str
    details: dict[str, Any] | None
    bot_mode: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: str
    admin_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class TelegramDeliveryLogOut(BaseModel):
    id: str
    admin_id: str | None
    message_type: str
    status: str
    skip_reason: str | None
    symbol: str | None
    chat_id_masked: str | None
    bot_id_masked: str | None
    error_message: str | None
    source: str
    details: dict[str, Any] | None
    created_at: datetime

    class Config:
        from_attributes = True
