"""BTC impuls islem API endpointleri."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin
from shared.distributed_lock import LockNotAcquiredError

from ...core.database import get_db
from ...core.redis import get_redis
from ...schemas.impulse import (
    ImpulseExecuteOut,
    ImpulseExecuteRequest,
    ImpulseScanOut,
    ImpulseSettingsOut,
    ImpulseSettingsUpdate,
)
from ...services.impulse_service import (
    get_impulse_settings,
    run_impulse_execute,
    run_impulse_scan,
    update_impulse_settings,
)
from ..deps import get_current_admin, require_csrf

router = APIRouter(prefix="/impulse", tags=["impulse"])


@router.get("/settings", response_model=ImpulseSettingsOut)
async def impulse_settings_get(
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    data = await get_impulse_settings(session, admin.id)
    return ImpulseSettingsOut(**data)


@router.put("/settings", response_model=ImpulseSettingsOut)
async def impulse_settings_put(
    payload: ImpulseSettingsUpdate,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
    _csrf=Depends(require_csrf),
):
    updates = payload.model_dump(exclude_unset=True)
    await update_impulse_settings(session, admin.id, updates, None)
    data = await get_impulse_settings(session, admin.id)
    return ImpulseSettingsOut(**data)


@router.post("/scan", response_model=ImpulseScanOut)
async def impulse_scan(
    side: str | None = None,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
    _csrf=Depends(require_csrf),
):
    try:
        result = await run_impulse_scan(session, admin.id, manual_side=side)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ImpulseScanOut(
        btc_direction=result.btc_direction,
        btc_change_pct=result.btc_change_pct,
        counter_side=result.counter_side,
        cooldown_active=result.cooldown_active,
        message=result.message,
        candidates=[
            {
                "symbol": c.symbol,
                "side": c.side,
                "score": c.score,
                "rsi": c.rsi,
                "proximity_pct": c.proximity_pct,
                "volume_ratio": c.volume_ratio,
                "price": c.price,
                "reason": c.reason,
            }
            for c in result.candidates
        ],
    )


@router.post("/execute", response_model=ImpulseExecuteOut)
async def impulse_execute(
    payload: ImpulseExecuteRequest,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    admin: Admin = Depends(get_current_admin),
    _csrf=Depends(require_csrf),
):
    try:
        result = await run_impulse_execute(
            session,
            redis,
            admin.id,
            manual_side=payload.side,
            symbols=payload.symbols,
            max_entries=payload.max_entries,
            admin_id=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LockNotAcquiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ImpulseExecuteOut(**result)
