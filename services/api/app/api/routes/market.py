from __future__ import annotations



from fastapi import APIRouter, Depends, Query



from sqlalchemy.ext.asyncio import AsyncSession



from shared.db import Admin



from ...core.config import Settings, get_settings
from ...core.database import get_db
from ...schemas.market import MarketAiResearchOut, MarketOverviewOut, MarketRegimeOut
from ...services.market_ai_service import run_market_ai_research
from ...services.market_helpers import fetch_market_regime_out
from ...services.market_overview_service import fetch_market_overview
from ..deps import get_current_admin, get_redis_dep, require_csrf

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/overview", response_model=MarketOverviewOut)
async def get_market_overview(
    force_refresh: bool = Query(default=False, description="Onbellegi atla"),
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
    app_settings: Settings = Depends(get_settings),
    redis=Depends(get_redis_dep),
) -> MarketOverviewOut:
    """Futures evreni genisligi, alim/satim baskisi ve BTC ozeti."""
    return await fetch_market_overview(
        session,
        app_settings,
        redis,
        force_refresh=force_refresh,
    )


@router.get("/regime", response_model=MarketRegimeOut)
async def get_market_regime(
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
    app_settings: Settings = Depends(get_settings),
) -> MarketRegimeOut:
    """BTC tabanli kisa vadeli piyasa yonu (LONG / SHORT / NEUTRAL)."""
    return await fetch_market_regime_out(session, app_settings)


@router.post("/ai-research", response_model=MarketAiResearchOut, dependencies=[Depends(require_csrf)])
async def post_market_ai_research(
    force_refresh: bool = Query(default=False, description="Onbellegi atla"),
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
    app_settings: Settings = Depends(get_settings),
    redis=Depends(get_redis_dep),
) -> MarketAiResearchOut:
    """GPT ile piyasa arastirmasi — emir karari vermez, yalnizca analiz."""
    return await run_market_ai_research(
        session,
        app_settings,
        redis,
        force_refresh=force_refresh,
    )


