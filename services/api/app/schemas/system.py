from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    app_env: str
    version: str = "1.0.0"


class ComponentHealthOut(BaseModel):
    component: str
    status: str
    message: str | None
    checked_at: datetime | None


class SystemStatusOut(BaseModel):
    overall_status: str
    components: list[ComponentHealthOut]


class TelegramTestOut(BaseModel):
    ok: bool
    message: str
    configured: bool
