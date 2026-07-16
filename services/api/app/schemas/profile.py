from __future__ import annotations

from datetime import datetime

from typing import Any

from pydantic import BaseModel, Field


class ProfileConnectionsSummary(BaseModel):
    binance_configured: bool = False
    binance_source: str | None = None
    telegram_configured: bool = False
    telegram_source: str | None = None
    openai_configured: bool = False
    openai_source: str | None = None


class ProfileOut(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    last_login_at: datetime | None = None
    connections_unlocked: bool = False
    connections_summary: ProfileConnectionsSummary
    firebase_uid: str | None = None
    account_type: str = "customer"


class ProfileUnlockRequest(BaseModel):
    password: str = Field(min_length=1, max_length=64)


class ProfileUnlockResponse(BaseModel):
    ok: bool
    connections_unlocked: bool
    expires_in_seconds: int


class ProfileConnectionsOut(BaseModel):
    binance_api_key_masked: str | None = None
    binance_api_secret_set: bool = False
    binance_configured: bool = False
    binance_source: str | None = None

    telegram_bot_token_masked: str | None = None
    telegram_chat_id: str | None = None
    telegram_notifications_enabled: bool = False
    telegram_configured: bool = False
    telegram_source: str | None = None

    openai_api_key_masked: str | None = None
    openai_configured: bool = False
    openai_source: str | None = None


class ProfileConnectionsUpdate(BaseModel):
    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_notifications_enabled: bool | None = None
    openai_api_key: str | None = None


class ProfileFullNameUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)


class ProfileTestResult(BaseModel):
    ok: bool
    message: str


class TelegramDiscoverChatIdRequest(BaseModel):
    telegram_bot_token: str | None = None


class TelegramDiscoverChatIdResponse(BaseModel):
    ok: bool
    chat_id: str | None = None
    message: str


class ProfileTelegramDeliveryLogOut(BaseModel):
    id: str
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
