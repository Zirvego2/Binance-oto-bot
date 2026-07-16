from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance import BinanceApiError, BinanceConnectionError, BinanceNotConfiguredError
from shared.db import Admin

from ...core.binance_client import get_binance_adapter_for_admin, is_binance_configured_for_admin
from ...core.database import get_db
from ...schemas.binance import (
    BinanceAccountBalanceOut,
    BinanceAccountInfoOut,
    BinanceOrderOut,
    BinancePositionOut,
    BinanceStatusOut,
    ReconciliationRunOut,
)
from ...services.binance_status_service import get_or_create_status_row, test_connection_and_persist
from ...services.paper_state_service import (
    get_paper_account_info,
    get_paper_balances,
    get_paper_open_algo_orders,
    get_paper_open_orders,
    get_paper_open_positions,
)
from ...services.reconciliation_service import run_and_persist_reconciliation
from ...services.settings_service import get_or_create_bot_settings
from ..deps import get_current_admin, require_csrf

router = APIRouter(prefix="/binance", tags=["binance"])


async def _current_environment(session: AsyncSession, admin_id: str) -> str:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    return settings_row.mode


def _row_to_status_out(row, environment: str) -> BinanceStatusOut:
    out = BinanceStatusOut(
        environment=environment,
        is_configured=row.is_configured,
        is_connected=row.is_connected,
        account_access_ok=row.account_access_ok,
        futures_account_usable=row.futures_account_usable,
        trading_permission_ok=row.trading_permission_ok,
        position_mode_verified=row.position_mode_verified,
        multi_assets_mode_off_verified=row.multi_assets_mode_off_verified,
        last_success_at=row.last_success_at,
        last_error_at=row.last_error_at,
        last_error_message=row.last_error_message,
    )
    if not row.is_configured:
        out.not_configured_message = "Binance API bilgileri henuz eklenmedi"
    return out


@router.post("/test-connection", response_model=BinanceStatusOut, dependencies=[Depends(require_csrf)])
async def test_connection(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> BinanceStatusOut:
    environment = await _current_environment(session, admin.id)
    row = await test_connection_and_persist(session, admin.id, environment)
    return _row_to_status_out(row, environment)


@router.get("/status", response_model=BinanceStatusOut)
async def get_status(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> BinanceStatusOut:
    environment = await _current_environment(session, admin.id)
    row = await get_or_create_status_row(session, admin.id, environment)
    return _row_to_status_out(row, environment)


async def _require_configured(session: AsyncSession, admin_id: str, environment: str) -> None:
    if not await is_binance_configured_for_admin(session, admin_id, environment):
        raise HTTPException(status_code=409, detail="Binance API bilgileri henuz eklenmedi (profil baglantilari)")


@router.get("/account", response_model=BinanceAccountInfoOut)
async def get_account(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> BinanceAccountInfoOut:
    environment = await _current_environment(session, admin.id)
    if environment == "paper":
        return await get_paper_account_info(session, admin.id)
    await _require_configured(session, admin.id, environment)
    adapter = await get_binance_adapter_for_admin(session, admin.id, environment)
    try:
        info = await adapter.get_account_info()
    except (BinanceApiError, BinanceConnectionError, BinanceNotConfiguredError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return BinanceAccountInfoOut(
        total_wallet_balance=info.total_wallet_balance,
        total_unrealized_pnl=info.total_unrealized_pnl,
        total_margin_balance=info.total_margin_balance,
        available_balance=info.available_balance,
        can_trade=info.can_trade,
        multi_assets_margin=info.multi_assets_margin,
    )


@router.get("/balance", response_model=list[BinanceAccountBalanceOut])
async def get_balance(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> list[BinanceAccountBalanceOut]:
    environment = await _current_environment(session, admin.id)
    if environment == "paper":
        return await get_paper_balances(session, admin.id)
    await _require_configured(session, admin.id, environment)
    adapter = await get_binance_adapter_for_admin(session, admin.id, environment)
    try:
        balances = await adapter.get_account_balance()
    except (BinanceApiError, BinanceConnectionError, BinanceNotConfiguredError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [
        BinanceAccountBalanceOut(
            asset=b.asset, wallet_balance=b.wallet_balance, available_balance=b.available_balance,
            unrealized_pnl=b.unrealized_pnl,
        )
        for b in balances
    ]


@router.get("/positions", response_model=list[BinancePositionOut])
async def get_positions(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> list[BinancePositionOut]:
    environment = await _current_environment(session, admin.id)
    if environment == "paper":
        return await get_paper_open_positions(session, admin.id)
    await _require_configured(session, admin.id, environment)
    adapter = await get_binance_adapter_for_admin(session, admin.id, environment)
    try:
        positions = await adapter.get_open_positions()
    except (BinanceApiError, BinanceConnectionError, BinanceNotConfiguredError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [
        BinancePositionOut(
            symbol=p.symbol, position_side="LONG" if p.quantity > 0 else "SHORT", quantity=abs(p.quantity),
            entry_price=p.entry_price, mark_price=p.mark_price, unrealized_pnl=p.unrealized_pnl,
            leverage=p.leverage, margin_type=p.margin_type, liquidation_price=p.liquidation_price,
        )
        for p in positions
    ]


@router.get("/open-orders", response_model=list[BinanceOrderOut])
async def get_open_orders(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> list[BinanceOrderOut]:
    environment = await _current_environment(session, admin.id)
    if environment == "paper":
        return await get_paper_open_orders(session, admin.id)
    await _require_configured(session, admin.id, environment)
    adapter = await get_binance_adapter_for_admin(session, admin.id, environment)
    try:
        orders = await adapter.get_open_orders()
    except (BinanceApiError, BinanceConnectionError, BinanceNotConfiguredError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [_to_order_out(o) for o in orders]


@router.get("/open-algo-orders", response_model=list[BinanceOrderOut])
async def get_open_algo_orders(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> list[BinanceOrderOut]:
    environment = await _current_environment(session, admin.id)
    if environment == "paper":
        return await get_paper_open_algo_orders(session, admin.id)
    await _require_configured(session, admin.id, environment)
    adapter = await get_binance_adapter_for_admin(session, admin.id, environment)
    try:
        orders = await adapter.get_open_algo_orders()
    except (BinanceApiError, BinanceConnectionError, BinanceNotConfiguredError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [_to_order_out(o) for o in orders]


def _to_order_out(o) -> BinanceOrderOut:
    return BinanceOrderOut(
        symbol=o.symbol, binance_order_id=o.binance_order_id, client_order_id=o.client_order_id,
        side=o.side, order_type=o.order_type, status=o.status, price=o.price, orig_qty=o.orig_qty,
        executed_qty=o.executed_qty,
    )


@router.post("/reconcile", response_model=ReconciliationRunOut, dependencies=[Depends(require_csrf)])
async def trigger_reconciliation(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> ReconciliationRunOut:
    environment = await _current_environment(session, admin.id)
    if environment == "paper":
        # PAPER modunda "gercek borsa" veritabaninin kendisidir; ayri bir
        # exchange kaynagi olmadigi icin reconciliation anlamsizdir.
        raise HTTPException(
            status_code=409,
            detail="PAPER modunda reconciliation calistirilamaz (gercek borsa hesabi yok)",
        )
    await _require_configured(session, admin.id, environment)
    run = await run_and_persist_reconciliation(session, admin.id, environment, triggered_by="manual")
    return ReconciliationRunOut.model_validate(run)
