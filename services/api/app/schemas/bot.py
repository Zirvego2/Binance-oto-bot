from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BotStatusOut(BaseModel):
    bot_enabled: bool
    mode: str
    run_state: str
    started_at: datetime | None
    safe_mode_reason: str | None
    worker_heartbeat_at: datetime | None
    worker_connected: bool = False
    worker_stale_seconds: int | None = None


class EmergencyStopRequest(BaseModel):
    close_all_positions: bool = False
    confirmation_text: str | None = None


class EmergencyStopResponse(BaseModel):
    run_state: str
    closed_positions: list[str]
    failed_positions: list[str]


class ChangeModeRequest(BaseModel):
    target_mode: str
    confirmation_text: str | None = None
    risk_ack: bool = False


class ChangeModeResponse(BaseModel):
    mode: str
    message: str
