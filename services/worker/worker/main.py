"""Worker servisi ana giris noktasi.

Bu surec; piyasa verisi senkronizasyonu, sinyal taramasi, risk kontrolu,
emir/algo-emir yonetimi, pozisyon izleme ve reconciliation gorevlerini
asenkron olarak birlikte yurutur. Tek bir worker instance'inin kritik
islemleri (tarama+emir) yapmasini garanti etmek icin Redis dagitik kilit
kullanilir (sartname bolum 24).

ONEMLI: Bu sistem kazanc garantisi vermez.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import signal
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy import select

from shared.binance import BinanceAdapterConfig, BinanceFuturesAdapter, build_adapter
from shared.db import BotEvent, BotRuntimeStatus, BotSettings, Symbol
from shared.process_lock import ensure_single_instance, release_service_lock
from shared.system_health import upsert_system_health

from .impulse_loop import impulse_auto_cycle
from .config import get_worker_settings
from .db import AsyncSessionLocal, create_all_tables, session_scope
from .mark_price_stream import run_mark_price_stream
from .market_regime import fetch_btc_market_regime, select_best_signal_for_regime
from .signal_selection import select_latest_signal_for_trade
from .market_sync import refresh_market_data, refresh_spread_and_oi, sync_exchange_info
from .order_engine import PositionOpenSkipped, monitor_limit_entries, open_position_for_signal, open_position_limit_entry
from .position_monitor import process_position_on_mark_tick, refresh_open_positions
from .reconciliation_task import run_reconciliation
from .redis_lock import DistributedLock
from .strategy import analyze_symbol, select_candidate_symbols

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_RUN_DIR = Path(__file__).resolve().parents[3] / ".run"
_RUN_DIR.mkdir(parents=True, exist_ok=True)
_file_handler = logging.handlers.RotatingFileHandler(
    _RUN_DIR / "worker_app.log", maxBytes=20 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, handlers=[logging.StreamHandler(), _file_handler])
logger = logging.getLogger("worker.main")

WORKER_ID = uuid.uuid4().hex[:12]


def _build_adapter_config(settings, bot_mode: str, api_key: str, api_secret: str) -> BinanceAdapterConfig:
    return BinanceAdapterConfig(
        binance_env=bot_mode,
        live_base_url=settings.binance_futures_base_url,
        live_api_key=api_key,
        live_api_secret=api_secret,
        demo_base_url=settings.binance_demo_base_url,
        demo_api_key=api_key,
        demo_api_secret=api_secret,
        paper_market_base_url=settings.binance_futures_base_url,
        paper_start_balance_usdt=Decimal(settings.paper_start_balance_usdt),
        paper_taker_commission_rate=Decimal(settings.paper_taker_commission_rate),
    )


async def _resolve_binance_credentials(settings) -> tuple[str, str]:
    from shared.customer_credentials import (
        bootstrap_profile_from_environment,
        environment_credentials_from_settings,
        get_primary_admin_profile,
        profile_binance_credentials,
    )

    env = environment_credentials_from_settings(settings)
    async with session_scope() as session:
        profile = await get_primary_admin_profile(session)
        if profile is None:
            from sqlalchemy import select
            from shared.db import Admin

            admin_row = await session.execute(select(Admin).limit(1))
            admin = admin_row.scalar_one_or_none()
            if admin is not None:
                profile = await bootstrap_profile_from_environment(
                    session,
                    admin.id,
                    env,
                    encryption_key=settings.app_encryption_key,
                    app_secret=settings.app_secret,
                )
        creds = profile_binance_credentials(
            profile,
            encryption_key=settings.app_encryption_key,
            app_secret=settings.app_secret,
            env=env,
        )
    if creds:
        return creds.api_key, creds.api_secret
    return settings.binance_api_key, settings.binance_api_secret


def _ws_base_url_for_mode(settings, bot_mode: str) -> str:
    return settings.binance_demo_ws_url if bot_mode == "demo" else settings.binance_futures_ws_url


async def _resolve_startup_bot_mode(settings) -> str:
    """Worker'in calisacagi mod: DB'deki ``BotSettings.mode`` degeri tek
    dogru kaynaktir (admin panelinden yonetilir). DB'de henuz ayar yoksa
    ``BINANCE_ENV`` ortam degiskeni varsayilan olarak kullanilir.

    NOT: Mod degisikligi (ornegin paper -> live) worker sureci CALISIRKEN
    otomatik uygulanmaz; guvenlik nedeniyle worker'in yeniden baslatilmasi
    gerekir (bkz. README "Mod Degistirme" bolumu). Bu, LIVE moda gecis icin
    ekstra bir guvenlik katmani olarak bilerek tasarlanmistir.
    """

    settings_row = await _get_bot_settings()
    if settings_row is not None:
        return settings_row.mode
    return settings.binance_env


async def _get_bot_settings() -> BotSettings | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
        return result.scalar_one_or_none()


async def heartbeat_loop(stop_event: asyncio.Event, interval_seconds: int) -> None:
    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                runtimes = (
                    await session.execute(
                        select(BotRuntimeStatus).where(BotRuntimeStatus.admin_id.is_not(None))
                    )
                ).scalars().all()
                now = datetime.now(timezone.utc)
                for runtime in runtimes:
                    runtime.worker_heartbeat_at = now
                await upsert_system_health(session, "worker", "OK", f"heartbeat {WORKER_ID}")
        except Exception:  # noqa: BLE001
            logger.exception("Heartbeat guncellenemedi")
        await asyncio.sleep(interval_seconds)


async def mark_price_tick_handler(_adapter: BinanceFuturesAdapter, tick, bot_mode: str, worker_settings) -> None:
    try:
        async with session_scope() as session:
            await process_position_on_mark_tick(
                session, bot_mode, tick.symbol, tick.mark_price, worker_settings=worker_settings
            )
    except Exception:  # noqa: BLE001
        logger.exception("Mark price tick pozisyon izleme hatasi (%s)", tick.symbol)


async def _get_platform_scan_settings(session) -> BotSettings | None:
    result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    result = await session.execute(select(BotSettings).order_by(BotSettings.created_at.asc()).limit(1))
    return result.scalar_one_or_none()


async def platform_scan_cycle(
    adapter: BinanceFuturesAdapter, bot_mode: str, redis: Redis, settings_template: BotSettings
) -> datetime | None:
    """Tum musteriler icin tek ortak analiz/sinyal taramasi. Tarama baslangic zamanini dondurur."""
    scan_started = datetime.now(timezone.utc)
    async with session_scope() as session:
        settings_row = settings_template
        if settings_row.mode != bot_mode:
            logger.debug("Platform tarama atlandi (sablon modu %s, worker modu %s)", settings_row.mode, bot_mode)
            return None

        candidates = await select_candidate_symbols(session, settings_row)
        if candidates:
            await refresh_spread_and_oi(session, adapter, [c.symbol for c in candidates])

        filter_enabled = bool(getattr(settings_row, "market_direction_filter_enabled", False))
        market_regime = await fetch_btc_market_regime(adapter) if filter_enabled else None

        trade_candidates: list[tuple[Symbol, object]] = []
        scan_signals: list[tuple[str, object, dict]] = []
        for symbol_row in candidates:
            try:
                signal_result = await analyze_symbol(
                    session, adapter, settings_row, symbol_row, platform_shared=True
                )
            except Exception:  # noqa: BLE001
                logger.exception("%s analiz edilirken hata olustu", symbol_row.symbol)
                continue
            if signal_result is None:
                continue
            if signal_result.suggested_side is not None:
                ctx = {
                    "mark_price": float(symbol_row.mark_price or 0),
                    "spread_pct": float(symbol_row.spread_pct or 0),
                    "volume_24h": float(symbol_row.volume_24h_usdt or 0),
                    "funding_rate_pct": float((symbol_row.funding_rate or 0)) * 100,
                    "closes": [],
                }
                scan_signals.append((symbol_row.symbol, signal_result, ctx))
                trade_candidates.append((symbol_row, signal_result))

        market_direction = market_regime.direction if market_regime else None
        best_signal = select_best_signal_for_regime(
            trade_candidates,
            filter_enabled=filter_enabled,
            market_direction=market_direction,
        )

        try:
            from .enhanced_scan_service import enrich_signals_from_enhanced_scan, run_enhanced_scan_cycle

            enhanced_result = await run_enhanced_scan_cycle(
                session,
                adapter,
                settings_row,
                scan_signals=scan_signals,
                current_best=(best_signal[0].symbol, best_signal[1]) if best_signal else None,
                redis=redis,
            )
            if enhanced_result:
                await enrich_signals_from_enhanced_scan(session, enhanced_result, settings_row.mode, admin_id=None)
        except Exception:  # noqa: BLE001
            logger.exception("Enhanced scan cycle hatasi (mevcut motor devam ediyor)")

    return scan_started


async def tenant_trade_cycle(
    adapter: BinanceFuturesAdapter,
    bot_mode: str,
    lock: DistributedLock,
    redis: Redis,
    admin_id: str,
    *,
    signals_since: datetime | None = None,
) -> None:
    """Musteri bazli otomatik islem — ortak sinyal havuzundan secer."""
    async with session_scope() as session:
        from shared.firestore.settings_hydrate import hydrate_bot_settings_from_firestore

        result = await session.execute(select(BotSettings).where(BotSettings.admin_id == admin_id))
        settings_row = result.scalar_one_or_none()
        if settings_row is None:
            return
        settings_row = await hydrate_bot_settings_from_firestore(session, settings_row, admin_id)

        if settings_row.mode != bot_mode:
            return

        runtime_result = await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.admin_id == admin_id))
        runtime = runtime_result.scalar_one_or_none()
        if runtime is not None and runtime.run_state in ("SAFE_MODE", "EMERGENCY_STOPPED"):
            return
        if not settings_row.bot_enabled:
            return

        filter_enabled = bool(getattr(settings_row, "market_direction_filter_enabled", False))
        market_regime = await fetch_btc_market_regime(adapter) if filter_enabled else None
        market_direction = market_regime.direction if market_regime else None

        if runtime is not None:
            runtime.last_scan_at = datetime.now(timezone.utc)

        trade_pick = await select_latest_signal_for_trade(
            session,
            settings_row,
            admin_id,
            filter_enabled=filter_enabled,
            market_direction=market_direction,
            signals_since=signals_since,
        )

        if trade_pick is None or not settings_row.auto_trading_enabled:
            return

        symbol_row, signal_row = trade_pick
        if runtime is not None:
            runtime.last_signal_at = datetime.now(timezone.utc)

        acquired = await lock.acquire(blocking_timeout_seconds=3.0)
        if not acquired:
            logger.warning("Islem kilidi alinamadi, bu dongu atlaniyor (admin=%s)", admin_id)
            return
        try:
            use_limit_entry = getattr(settings_row, "limit_entry_enabled", False)
            try:
                if use_limit_entry:
                    order = await open_position_limit_entry(
                        session, adapter, settings_row, symbol_row, signal_row.side,
                        signal_row.id, "latest_signal",
                        signal_row.total_score,
                    )
                    logger.info(
                        "Olta emri verildi (%s), dolum bekleniyor (status=%s)",
                        order.client_order_id, order.status,
                    )
                    await session.commit()
                else:
                    position = await open_position_for_signal(
                        session, adapter, settings_row, symbol_row, signal_row.side,
                        signal_row.id, "latest_signal",
                        signal_row.total_score,
                    )
                    await session.commit()
                    logger.info("Pozisyon acildi: %s %s (admin=%s)", symbol_row.symbol, signal_row.side, admin_id)
            except PositionOpenSkipped as exc:
                logger.info("%s icin islem atlandi (admin=%s): %s", symbol_row.symbol, admin_id, exc.reason)
        finally:
            await lock.release()


async def scan_and_trade_cycle(
    adapter: BinanceFuturesAdapter, bot_mode: str, lock: DistributedLock, redis: Redis, admin_id: str
) -> None:
    """Geriye uyumluluk: yalnizca musteri islem dongusu."""
    await tenant_trade_cycle(adapter, bot_mode, lock, redis, admin_id)


async def tenant_position_monitor_loop(settings, stop_event: asyncio.Event, interval_seconds: int) -> None:
    from shared.tenant_settings import list_active_tenant_admins

    from .tenant_ops import build_adapter_for_admin

    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                tenants = await list_active_tenant_admins(
                    session,
                    encryption_key=settings.app_encryption_key,
                    app_secret=settings.app_secret,
                )
                for admin in tenants:
                    row = await session.execute(
                        select(BotSettings).where(BotSettings.admin_id == admin.id)
                    )
                    settings_row = row.scalar_one_or_none()
                    if settings_row is None:
                        continue
                    try:
                        adapter = await build_adapter_for_admin(
                            session, settings, admin.id, settings_row.mode
                        )
                        await refresh_open_positions(
                            session, adapter, settings_row.mode, admin.id
                        )
                    except Exception:  # noqa: BLE001
                        logger.exception("Pozisyon izleme hatasi (admin=%s)", admin.id)
        except Exception:  # noqa: BLE001
            logger.exception("Pozisyon izleme dongusunde hata")
        await asyncio.sleep(interval_seconds)


async def scan_loop(
    settings, redis: Redis, stop_event: asyncio.Event, bot_mode: str, market_adapter: BinanceFuturesAdapter
) -> None:
    from shared.tenant_settings import list_active_tenant_admins

    from .tenant_ops import build_adapter_for_admin

    while not stop_event.is_set():
        interval = 60
        try:
            async with session_scope() as session:
                scan_template = await _get_platform_scan_settings(session)
                tenants = await list_active_tenant_admins(
                    session,
                    encryption_key=settings.app_encryption_key,
                    app_secret=settings.app_secret,
                )
                if scan_template is not None:
                    interval = max(scan_template.scan_interval_seconds, 5)

            scan_started: datetime | None = None
            if scan_template is not None:
                platform_lock = DistributedLock(redis, "trading_engine:platform_scan", ttl_seconds=120)
                acquired = await platform_lock.acquire(blocking_timeout_seconds=5.0)
                if acquired:
                    try:
                        scan_started = await platform_scan_cycle(market_adapter, bot_mode, redis, scan_template)
                    finally:
                        await platform_lock.release()

            for admin in tenants:
                async with session_scope() as session:
                    row = (
                        await session.execute(select(BotSettings).where(BotSettings.admin_id == admin.id))
                    ).scalar_one_or_none()
                    if row is None:
                        continue
                    tenant_mode = row.mode
                    adapter = await build_adapter_for_admin(session, settings, admin.id, tenant_mode)
                tenant_lock = DistributedLock(redis, f"trading_engine:{admin.id}", ttl_seconds=30)
                await tenant_trade_cycle(
                    adapter, tenant_mode, tenant_lock, redis, admin.id, signals_since=scan_started
                )
        except Exception:  # noqa: BLE001
            logger.exception("Tarama dongusunde beklenmeyen hata")
        await asyncio.sleep(interval)


async def market_sync_loop(adapter: BinanceFuturesAdapter, stop_event: asyncio.Event, interval_seconds: int) -> None:
    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                await sync_exchange_info(session, adapter)
                await refresh_market_data(session, adapter)
        except Exception:  # noqa: BLE001
            logger.exception("Piyasa verisi senkronizasyonunda hata")
        await asyncio.sleep(interval_seconds)


async def olta_monitor_loop(settings, stop_event: asyncio.Event, interval_seconds: int = 30) -> None:
    from shared.tenant_settings import list_active_tenant_admins

    from .tenant_ops import build_adapter_for_admin

    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                tenants = await list_active_tenant_admins(
                    session,
                    encryption_key=settings.app_encryption_key,
                    app_secret=settings.app_secret,
                )
                for admin in tenants:
                    settings_row = (
                        await session.execute(
                            select(BotSettings).where(BotSettings.admin_id == admin.id)
                        )
                    ).scalar_one_or_none()
                    if settings_row is None or not getattr(settings_row, "limit_entry_enabled", False):
                        continue
                    adapter = await build_adapter_for_admin(
                        session, settings, admin.id, settings_row.mode
                    )
                    await monitor_limit_entries(session, adapter, settings_row)
        except Exception:  # noqa: BLE001
            logger.exception("Olta izleme dongusunde hata")
        await asyncio.sleep(interval_seconds)


async def impulse_loop(settings, redis: Redis, stop_event: asyncio.Event) -> None:
    from shared.tenant_settings import list_active_tenant_admins

    from .tenant_ops import build_adapter_for_admin

    while not stop_event.is_set():
        interval = 20
        try:
            async with session_scope() as session:
                tenants = await list_active_tenant_admins(
                    session,
                    encryption_key=settings.app_encryption_key,
                    app_secret=settings.app_secret,
                )
            for admin in tenants:
                async with session_scope() as session:
                    settings_row = (
                        await session.execute(
                            select(BotSettings).where(BotSettings.admin_id == admin.id)
                        )
                    ).scalar_one_or_none()
                    if settings_row is None:
                        continue
                    interval = max(settings_row.impulse_check_interval_seconds, 5)
                    if settings_row.impulse_mode != "AUTO":
                        continue
                    adapter = await build_adapter_for_admin(
                        session, settings, admin.id, settings_row.mode
                    )
                    tenant_lock = DistributedLock(redis, f"trading_engine:{admin.id}", ttl_seconds=30)
                    await impulse_auto_cycle(session, adapter, settings_row, settings_row.mode, tenant_lock, redis)
        except Exception:  # noqa: BLE001
            logger.exception("Impuls dongusunde hata")
        await asyncio.sleep(interval)


async def reconciliation_loop(
    settings, stop_event: asyncio.Event, interval_seconds: int, bot_mode: str
) -> None:
    from shared.tenant_settings import list_reconciliation_tenant_admins

    from .tenant_ops import build_adapter_for_admin

    if bot_mode == "paper":
        return
    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                tenants = await list_reconciliation_tenant_admins(
                    session,
                    bot_mode,
                    encryption_key=settings.app_encryption_key,
                    app_secret=settings.app_secret,
                )
            for admin in tenants:
                try:
                    async with session_scope() as session:
                        adapter = await build_adapter_for_admin(session, settings, admin.id, bot_mode)
                        await run_reconciliation(session, adapter, bot_mode, admin.id, triggered_by="scheduled")
                except Exception:  # noqa: BLE001
                    logger.exception("Reconciliation hatasi (admin=%s)", admin.id)
        except Exception:  # noqa: BLE001
            logger.exception("Reconciliation gorevinde hata")
        await asyncio.sleep(interval_seconds)


async def mark_price_loop(
    adapter: BinanceFuturesAdapter, ws_base_url: str, stop_event: asyncio.Event, bot_mode: str, worker_settings
) -> None:
    async def handler(tick):
        await mark_price_tick_handler(adapter, tick, bot_mode, worker_settings)

    await run_mark_price_stream(ws_base_url, handler, stop_event)


async def _record_fatal_worker_error(message: str) -> None:
    try:
        async with session_scope() as session:
            runtime_result = await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.id == "default"))
            runtime = runtime_result.scalar_one_or_none()
            if runtime is None:
                runtime = BotRuntimeStatus(id="default")
                session.add(runtime)
            runtime.last_error_at = datetime.now(timezone.utc)
            runtime.last_error_message = message[:500]
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Fatal worker hatasi DB'ye yazilamadi")


async def main() -> None:
    lock_file = None
    if os.environ.get("SKIP_PROCESS_LOCK", "").lower() not in ("1", "true", "yes"):
        lock_file = ensure_single_instance("worker")
    settings = get_worker_settings()
    await create_all_tables()

    from pathlib import Path

    from shared.firestore import init_firebase

    repo_root = Path(__file__).resolve().parents[3]
    init_firebase(
        project_id=settings.firebase_project_id,
        service_account_path=settings.firebase_service_account_path,
        service_account_json=settings.firebase_service_account_json,
        repo_root=repo_root,
    )

    logger.info(
        "Worker baslatiliyor (instance=%s, binance_env=%s) - Bu sistem kazanc garantisi vermez.",
        WORKER_ID, settings.binance_env,
    )

    bot_mode = await _resolve_startup_bot_mode(settings)
    logger.info("Worker calisma modu: %s (degistirmek icin admin panelinden mod degistirip worker'i yeniden baslatin)", bot_mode)

    api_key, api_secret = await _resolve_binance_credentials(settings)
    adapter_config = _build_adapter_config(settings, bot_mode, api_key, api_secret)
    adapter = build_adapter(adapter_config)
    ws_base_url = _ws_base_url_for_mode(settings, bot_mode)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    lock = DistributedLock(redis, "trading_engine", ttl_seconds=30)

    async with session_scope() as session:
        session.add(BotEvent(event_type="BOT_STARTED", message=f"Worker basladi (instance={WORKER_ID}, mode={bot_mode})", bot_mode=bot_mode))
        result = await session.execute(select(Symbol))
        has_symbols = result.first() is not None
    if not has_symbols:
        async with session_scope() as session:
            await sync_exchange_info(session, adapter)
            await refresh_market_data(session, adapter)

    if bot_mode != "paper":
        from shared.tenant_settings import list_reconciliation_tenant_admins

        from .tenant_ops import build_adapter_for_admin

        async with session_scope() as session:
            tenants = await list_reconciliation_tenant_admins(
                session,
                bot_mode,
                encryption_key=settings.app_encryption_key,
                app_secret=settings.app_secret,
            )
        for admin in tenants:
            try:
                async with session_scope() as session:
                    tenant_adapter = await build_adapter_for_admin(session, settings, admin.id, bot_mode)
                    await run_reconciliation(session, tenant_adapter, bot_mode, admin.id, triggered_by="startup")
            except Exception:  # noqa: BLE001
                logger.exception("Baslangic reconciliation (admin=%s)", admin.id)

    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()

    def _handle_signal() -> None:
        logger.info("Kapanma sinyali alindi, worker durduruluyor...")
        stop_event.set()

    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                loop.add_signal_handler(sig, _handle_signal)  # type: ignore[attr-defined]
            except (NotImplementedError, AttributeError):
                try:
                    signal.signal(sig, lambda *_: _handle_signal())
                except (ValueError, OSError):
                    pass

    tasks = [
        asyncio.create_task(heartbeat_loop(stop_event, settings.heartbeat_interval_seconds), name="heartbeat"),
        asyncio.create_task(market_sync_loop(adapter, stop_event, settings.market_sync_interval_seconds), name="market_sync"),
        asyncio.create_task(scan_loop(settings, redis, stop_event, bot_mode, adapter), name="scan"),
        asyncio.create_task(tenant_position_monitor_loop(settings, stop_event, 1), name="position_monitor"),
        asyncio.create_task(olta_monitor_loop(settings, stop_event, 30), name="olta_monitor"),
        asyncio.create_task(impulse_loop(settings, redis, stop_event), name="impulse"),
        asyncio.create_task(
            reconciliation_loop(settings, stop_event, settings.reconciliation_interval_seconds, bot_mode),
            name="reconciliation",
        ),
        asyncio.create_task(
            mark_price_loop(adapter, ws_base_url, stop_event, bot_mode, settings), name="mark_price_ws"
        ),
    ]

    try:
        await stop_event.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        async with session_scope() as session:
            session.add(BotEvent(event_type="BOT_STOPPED", message=f"Worker durdu (instance={WORKER_ID})", bot_mode=bot_mode))
        await redis.aclose()
        release_service_lock(lock_file)
        logger.info("Worker durduruldu")


if __name__ == "__main__":
    # Cloud Run worker container: PORT=8080 ile health probe.
    # Yerel gelistirmede (start_bot.ps1) PORT yok — gereksiz 8080 dinleyicisi acma.
    if os.environ.get("ALL_IN_ONE", "").lower() not in ("1", "true", "yes"):
        health_port_raw = os.environ.get("WORKER_HEALTH_PORT") or os.environ.get("PORT")
        if health_port_raw:
            from .health_server import start_health_server

            start_health_server(int(health_port_raw))
    try:
        asyncio.run(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Worker beklenmeyen hatayla kapandi")
        try:
            asyncio.run(_record_fatal_worker_error(f"Worker crash: {exc}"))
        except Exception:  # noqa: BLE001
            pass
        raise SystemExit(1) from exc
