"""Gercek zamanli dashboard/pozisyon guncellemeleri (musteri bazli)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from shared.db import AdminSession, Position

from ...core.config import get_settings
from ...core.database import AsyncSessionLocal
from ...core.security import hash_session_token
from ...services.dashboard_service import build_dashboard
from ...services.position_sync_service import sync_positions_if_live_open
from ...services.settings_service import get_or_create_bot_settings

router = APIRouter(tags=["realtime"])

PUSH_INTERVAL_SECONDS = 1.0


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


async def _resolve_admin_id(websocket: WebSocket) -> str | None:
    settings = get_settings()
    token = websocket.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    token_hash = hash_session_token(token)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AdminSession).where(AdminSession.token_hash == token_hash))
        admin_session = result.scalar_one_or_none()
        if admin_session is None or admin_session.revoked_at is not None:
            return None
        expires_at = admin_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
        return admin_session.admin_id


@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket) -> None:
    admin_id = await _resolve_admin_id(websocket)
    if admin_id is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    try:
        while True:
            async with AsyncSessionLocal() as session:
                settings_row = await get_or_create_bot_settings(session, admin_id)
                await sync_positions_if_live_open(session, admin_id)
                dashboard_data = await build_dashboard(session, admin_id)
                positions_result = await session.execute(
                    select(Position).where(
                        Position.status == "OPEN",
                        Position.bot_mode == settings_row.mode,
                        Position.admin_id == admin_id,
                    )
                )
                positions = positions_result.scalars().all()
                exchange_open_count = len(positions)
                if settings_row.mode != "paper":
                    try:
                        from ...core.binance_client import get_binance_adapter_for_admin

                        adapter = await get_binance_adapter_for_admin(session, admin_id, settings_row.mode)
                        exchange_open_count = len(await adapter.get_open_positions())
                    except Exception:  # noqa: BLE001
                        pass
                payload = {
                    "type": "snapshot",
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "dashboard": dashboard_data,
                    "local_open_count": len(positions),
                    "exchange_open_count": exchange_open_count,
                    "open_positions": [
                        {
                            "id": p.id,
                            "symbol": p.symbol,
                            "side": p.side,
                            "entry_price": p.entry_price,
                            "mark_price": p.mark_price,
                            "unrealized_pnl": p.unrealized_pnl,
                            "roi_pct": p.roi_pct,
                        }
                        for p in positions
                    ],
                }
            await websocket.send_text(json.dumps(payload, cls=_DecimalEncoder))
            await asyncio.sleep(PUSH_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        return
