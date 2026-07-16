"""FastAPI uygulama giris noktasi.

Binance USDS-M Futures Otomatik Islem Botu - Backend API.

ONEMLI: Bu proje kazanc garantisi vermez. PAPER modu varsayilan calisma
modudur. LIVE moda gecis sadece cok asamali guvenlik kontrolunden gectikten
sonra mumkundur (bkz. app/services/bot_control_service.py).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.masking import mask_text

from .api.routes import (
    auth,
    avci,
    binance,
    bot,
    dashboard,
    enhanced,
    impulse,
    logs,
    market,
    orders,
    platform_admin,
    positions,
    profile,
    realtime,
)
from .api.routes import settings as settings_routes
from .api.routes import signals, symbols, system, trades
from .core.config import get_settings
from .core.database import create_all_tables, db_session_scope
from shared.system_health import upsert_system_health
from .core.logging import configure_logging, get_logger
from .core.middleware import SecurityHeadersMiddleware
from .core.redis import close_redis

configure_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings_obj = get_settings()
    if not settings_obj.is_production:
        await create_all_tables()
    from .core.firebase import init_firebase

    init_firebase(settings_obj)
    from .core.firebase import firebase_enabled

    if firebase_enabled():
        from shared.default_bot_settings import (
            DEFAULT_GENERAL_SETTINGS,
            DEFAULT_IMPULSE_SETTINGS,
            DEFAULT_POSITION_SETTINGS,
        )
        from shared.firestore import upsert_platform_defaults

        try:
            await upsert_platform_defaults(
                DEFAULT_GENERAL_SETTINGS,
                DEFAULT_POSITION_SETTINGS,
                DEFAULT_IMPULSE_SETTINGS,
            )
        except Exception:
            logger.warning("Platform varsayilanlari Firestore'a yazilamadi", exc_info=True)
    logger.info("API servisi baslatildi (app_env=%s, binance_env=%s)", settings_obj.app_env, settings_obj.binance_env)
    try:
        async with db_session_scope() as session:
            from .services.bootstrap_admin_service import ensure_bootstrap_admins

            await ensure_bootstrap_admins(session, settings_obj)
            await upsert_system_health(session, "api", "OK", "API servisi calisiyor")
            from .core.binance_client import refresh_binance_credentials_cache

            await refresh_binance_credentials_cache(session, settings_obj)
    except Exception:
        logger.warning("SystemHealth yazilamadi", exc_info=True)
    yield
    await close_redis()
    logger.info("API servisi durduruldu")


app = FastAPI(
    title="Binance USDS-M Futures Otomatik Islem Botu API",
    description=(
        "Bu sistem kazanc garantisi vermez. Kripto para vadeli islem ticareti "
        "yuksek risk icerir ve sermayenizin tamamini kaybedebilirsiniz."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.web_origin,
        *([] if settings.is_production else ["http://127.0.0.1:3000"]),
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.add_middleware(SecurityHeadersMiddleware, settings=settings)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Gecersiz istek verisi", "errors": exc.errors()})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, str):
        detail = mask_text(detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Beklenmeyen hata: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Sunucu hatasi olustu"})


API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(platform_admin.router, prefix=API_PREFIX)
app.include_router(profile.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(binance.router, prefix=API_PREFIX)
app.include_router(bot.router, prefix=API_PREFIX)
app.include_router(settings_routes.router, prefix=API_PREFIX)
app.include_router(symbols.router, prefix=API_PREFIX)
app.include_router(positions.router, prefix=API_PREFIX)
app.include_router(orders.router, prefix=API_PREFIX)
app.include_router(trades.router, prefix=API_PREFIX)
app.include_router(signals.router, prefix=API_PREFIX)
app.include_router(market.router, prefix=API_PREFIX)
app.include_router(logs.router, prefix=API_PREFIX)
app.include_router(system.router, prefix=API_PREFIX)
app.include_router(realtime.router, prefix=API_PREFIX)
app.include_router(enhanced.router, prefix=API_PREFIX)
app.include_router(impulse.router, prefix=API_PREFIX)
app.include_router(avci.router, prefix=API_PREFIX)
