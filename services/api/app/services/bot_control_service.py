"""Bot baslat/durdur/acil durdur/mod degistirme servisi (sartname bolum 20 & 21)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, BinanceConnectionStatus, BotRuntimeStatus, Position
from shared.membership import MEMBERSHIP_EXPIRED_MESSAGE, is_membership_active
from shared.tenant_settings import get_or_create_bot_runtime

from ..core.binance_client import get_binance_adapter_for_admin, is_binance_configured_for_admin
from ..core.config import Settings
from .audit_service import record_audit_log
from .position_service import close_position_manually
from .settings_service import get_or_create_bot_settings

EMERGENCY_STOP_CLOSE_ALL_CONFIRMATION = "TÜM POZİSYONLARI KAPAT"
LIVE_MODE_CONFIRMATION = "CANLI FUTURES İŞLEMİNİ AÇ"


async def _get_runtime(session: AsyncSession, admin_id: str) -> BotRuntimeStatus:
    return await get_or_create_bot_runtime(session, admin_id)


async def start_bot(session: AsyncSession, admin: Admin, ip_address: str | None) -> BotRuntimeStatus:
    if not is_membership_active(admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MEMBERSHIP_EXPIRED_MESSAGE,
        )
    settings_row = await get_or_create_bot_settings(session, admin.id)
    runtime = await _get_runtime(session, admin.id)

    if runtime.run_state == "SAFE_MODE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sistem SAFE_MODE durumunda (reconciliation tutarsizligi). Once tutarsizligi cozun.",
        )

    settings_row.bot_enabled = True
    runtime.run_state = "RUNNING"
    runtime.started_at = datetime.now(timezone.utc)
    runtime.stopped_at = None
    await session.commit()

    await record_audit_log(
        session, admin_id=admin.id, action="BOT_START", entity_type="bot", ip_address=ip_address
    )
    await session.refresh(runtime)
    return runtime


async def stop_bot(session: AsyncSession, admin: Admin, ip_address: str | None) -> BotRuntimeStatus:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    runtime = await _get_runtime(session, admin.id)

    settings_row.bot_enabled = False
    if runtime.run_state == "RUNNING":
        runtime.run_state = "STOPPED"
    runtime.stopped_at = datetime.now(timezone.utc)
    await session.commit()

    await record_audit_log(session, admin_id=admin.id, action="BOT_STOP", entity_type="bot", ip_address=ip_address)
    await session.refresh(runtime)
    return runtime


async def emergency_stop(
    session: AsyncSession,
    admin: Admin,
    close_all_positions: bool,
    confirmation_text: str | None,
    ip_address: str | None,
) -> dict:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    runtime = await _get_runtime(session, admin.id)

    if close_all_positions and confirmation_text != EMERGENCY_STOP_CLOSE_ALL_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tum pozisyonlari kapatmak icin tam olarak '{EMERGENCY_STOP_CLOSE_ALL_CONFIRMATION}' yazmalisiniz",
        )

    settings_row.bot_enabled = False
    runtime.run_state = "EMERGENCY_STOPPED"
    runtime.stopped_at = datetime.now(timezone.utc)

    closed_positions: list[str] = []
    failed_positions: list[str] = []

    if close_all_positions:
        result = await session.execute(
            select(Position).where(
                Position.status == "OPEN",
                Position.bot_mode == settings_row.mode,
                Position.admin_id == admin.id,
            )
        )
        open_positions = result.scalars().all()
        for position in open_positions:
            try:
                await close_position_manually(session, position.id, admin.id, "EMERGENCY_STOP", ip_address)
                closed_positions.append(position.symbol)
            except Exception:
                failed_positions.append(position.symbol)

    await session.commit()

    await record_audit_log(
        session,
        admin_id=admin.id,
        action="EMERGENCY_STOP",
        entity_type="bot",
        after_data={"close_all_positions": close_all_positions, "closed": closed_positions, "failed": failed_positions},
        ip_address=ip_address,
    )
    await session.refresh(runtime)

    return {
        "run_state": runtime.run_state,
        "closed_positions": closed_positions,
        "failed_positions": failed_positions,
    }


async def get_bot_status(session: AsyncSession, admin_id: str) -> dict:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    runtime = await _get_runtime(session, admin_id)
    from .dashboard_service import _worker_health

    worker = _worker_health(runtime)
    return {
        "bot_enabled": settings_row.bot_enabled,
        "mode": settings_row.mode,
        "run_state": runtime.run_state,
        "started_at": runtime.started_at,
        "safe_mode_reason": runtime.safe_mode_reason,
        "worker_heartbeat_at": runtime.worker_heartbeat_at,
        "worker_connected": worker["worker_connected"],
        "worker_stale_seconds": worker["worker_stale_seconds"],
    }


async def change_mode(
    session: AsyncSession,
    admin: Admin,
    target_mode: str,
    confirmation_text: str | None,
    risk_ack: bool,
    app_settings: Settings,
    redis: Redis,
    ip_address: str | None,
) -> dict:
    if target_mode not in ("paper", "demo", "live"):
        raise HTTPException(status_code=400, detail="Gecersiz mod. paper, demo veya live olmalidir")

    settings_row = await get_or_create_bot_settings(session, admin.id)
    runtime = await _get_runtime(session, admin.id)

    if target_mode == settings_row.mode:
        return {"mode": settings_row.mode, "message": "Mod zaten bu sekilde ayarli"}

    if target_mode == "demo" and not app_settings.enable_demo_trading:
        raise HTTPException(status_code=403, detail="DEMO islem ENABLE_DEMO_TRADING=false oldugu icin kapali")

    if target_mode == "live":
        await _validate_live_mode_checklist(
            session, admin, confirmation_text, risk_ack, app_settings, redis, settings_row, runtime
        )

    if runtime.run_state == "RUNNING":
        raise HTTPException(status_code=409, detail="Mod degistirmeden once botu durdurmalisiniz")

    before_mode = settings_row.mode
    settings_row.mode = target_mode
    settings_row.live_trading_enabled = target_mode == "live"
    if target_mode == "live":
        admin.live_trading_ack_at = datetime.now(timezone.utc)
    await session.commit()

    await record_audit_log(
        session,
        admin_id=admin.id,
        action="CHANGE_MODE",
        entity_type="bot_settings",
        before_data={"mode": before_mode},
        after_data={"mode": target_mode},
        ip_address=ip_address,
    )

    return {"mode": settings_row.mode, "message": f"Mod {target_mode.upper()} olarak degistirildi"}


async def _validate_live_mode_checklist(
    session: AsyncSession,
    admin: Admin,
    confirmation_text: str | None,
    risk_ack: bool,
    app_settings: Settings,
    redis: Redis,
    settings_row,
    runtime: BotRuntimeStatus,
) -> None:
    """Sartname bolum 21: LIVE moda gecis icin cok asamali guvenlik kontrolu."""

    problems: list[str] = []

    if not app_settings.enable_live_trading:
        problems.append("ENABLE_LIVE_TRADING=false (canli islem environment uzerinden kapali)")

    if not await is_binance_configured_for_admin(session, admin.id, "live"):
        problems.append("Binance API Key/Secret tanimlanmamis (profil baglantilari)")

    if not risk_ack:
        problems.append("Canli islem risk uyarisi onaylanmamis")

    if confirmation_text != LIVE_MODE_CONFIRMATION:
        problems.append(f"Onay metni hatali. Tam olarak '{LIVE_MODE_CONFIRMATION}' yazilmalidir")

    if runtime.run_state == "RUNNING":
        problems.append("Bot calisir durumda; once durdurulmali")

    open_paper_result = await session.execute(
        select(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == "paper",
            Position.admin_id == admin.id,
        )
    )
    if open_paper_result.scalars().first() is not None:
        problems.append("Acik PAPER pozisyonlari var; LIVE moda gecmeden once kapatilmali")

    try:
        await redis.ping()
    except Exception:
        problems.append("Redis baglantisi aktif degil")

    if not problems:
        try:
            adapter = await get_binance_adapter_for_admin(session, admin.id, "live")
            connection_result = await adapter.test_connection()
            if not connection_result.is_connected:
                problems.append(f"Binance baglanti testi basarisiz: {connection_result.error_message}")
            elif not connection_result.account_access_ok:
                problems.append("Futures hesap erisimi basarisiz")
            elif not connection_result.trading_permission_ok:
                problems.append("API anahtarinin islem (trading) yetkisi dogrulanamadi")
            else:
                await adapter.get_exchange_info()
                position_mode = await adapter.get_position_mode()
                if position_mode != "ONE_WAY":
                    problems.append("Binance hesabi ONE_WAY position mode'da degil")
                multi_assets = await adapter.get_multi_assets_mode()
                if multi_assets:
                    problems.append("Multi-Assets Mode acik; kapatilmalidir")
        except Exception as exc:
            problems.append(f"Binance dogrulamasi basarisiz: {exc}")

    if settings_row.daily_max_loss_usdt <= 0:
        problems.append("Gunluk maksimum zarar tanimlanmamis")
    if settings_row.margin_per_trade_usdt <= 0:
        problems.append("Islem basina teminat tanimlanmamis")
    if settings_row.max_allowed_leverage < 1:
        problems.append("Kaldirac sinirlari tanimlanmamis")
    if settings_row.take_profit_roi_pct <= 0 or settings_row.stop_loss_roi_pct <= 0:
        problems.append("Take-profit/Stop-loss ROI degerleri tanimlanmamis")
    if settings_row.max_open_positions < 1:
        problems.append("Maksimum acik pozisyon sayisi tanimlanmamis")

    if problems:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"message": "LIVE moda gecis kriterleri karsilanmadi", "problems": problems},
        )
