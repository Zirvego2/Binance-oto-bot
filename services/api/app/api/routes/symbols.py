from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance_filters import SymbolFilters, required_min_margin
from shared.db import Admin, Symbol, SymbolRule
from shared.tenant_scope import get_or_create_symbol_rule

from ...core.database import get_db
from ...schemas.market import SymbolOut, SymbolUpdateRequest
from ...services.audit_service import record_audit_log
from ...services.settings_service import get_or_create_bot_settings
from ..deps import get_current_admin, require_csrf

router = APIRouter(prefix="/symbols", tags=["symbols"])


def _default_symbol_rule(admin_id: str, symbol: str) -> SymbolRule:
    """DB'de kural yokken gecici kural — SQLAlchemy default'lari flush oncesi None kalabilir."""
    return SymbolRule(
        admin_id=admin_id,
        symbol=symbol,
        in_analysis_list=True,
        is_blacklisted=False,
        long_enabled=True,
        short_enabled=True,
    )


def _to_symbol_out(sym: Symbol, rule: SymbolRule, leverage: int) -> SymbolOut:
    required_margin = None
    if sym.last_price and sym.last_price > 0:
        filters = SymbolFilters(
            symbol=sym.symbol, status=sym.status, contract_type=sym.contract_type, quote_asset="USDT",
            margin_asset="USDT", price_tick_size=sym.price_tick_size, price_min=Decimal("0"),
            price_max=Decimal("0"), lot_step_size=sym.lot_step_size, lot_min_qty=sym.min_qty,
            lot_max_qty=sym.max_qty, market_lot_step_size=sym.market_lot_step_size, market_lot_min_qty=sym.min_qty,
            market_lot_max_qty=sym.max_qty, min_notional=sym.min_notional,
        )
        required_margin = required_min_margin(filters, sym.last_price, Decimal(leverage))

    return SymbolOut(
        symbol=sym.symbol, status=sym.status, contract_type=sym.contract_type, price_tick_size=sym.price_tick_size,
        lot_step_size=sym.lot_step_size, min_qty=sym.min_qty, min_notional=sym.min_notional,
        last_price=sym.last_price, mark_price=sym.mark_price, funding_rate=sym.funding_rate,
        volume_24h_usdt=sym.volume_24h_usdt, spread_pct=sym.spread_pct,
        in_analysis_list=bool(rule.in_analysis_list if rule.in_analysis_list is not None else True),
        is_blacklisted=bool(rule.is_blacklisted if rule.is_blacklisted is not None else False),
        blacklist_reason=rule.blacklist_reason,
        long_enabled=bool(rule.long_enabled if rule.long_enabled is not None else True),
        short_enabled=bool(rule.short_enabled if rule.short_enabled is not None else True), max_leverage_override=rule.max_leverage_override,
        last_signal_id=rule.last_signal_id, last_trade_at=rule.last_trade_at,
        required_min_margin_at_3x=required_margin,
    )


@router.get("", response_model=list[SymbolOut])
async def list_symbols(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> list[SymbolOut]:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    symbols_result = await session.execute(select(Symbol).order_by(Symbol.volume_24h_usdt.desc().nulls_last()))
    symbols = symbols_result.scalars().all()
    rules_result = await session.execute(select(SymbolRule).where(SymbolRule.admin_id == admin.id))
    rules_by_symbol = {r.symbol: r for r in rules_result.scalars().all()}

    out = []
    for sym in symbols:
        rule = rules_by_symbol.get(sym.symbol)
        if rule is None:
            rule = _default_symbol_rule(admin.id, sym.symbol)
        out.append(_to_symbol_out(sym, rule, settings_row.leverage))
    return out


@router.get("/{symbol}", response_model=SymbolOut)
async def get_symbol(
    symbol: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> SymbolOut:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    result = await session.execute(select(Symbol).where(Symbol.symbol == symbol.upper()))
    sym = result.scalar_one_or_none()
    if sym is None:
        raise HTTPException(status_code=404, detail="Sembol bulunamadi")
    rule = await get_or_create_symbol_rule(session, admin.id, symbol.upper())
    return _to_symbol_out(sym, rule, settings_row.leverage)


@router.patch("/{symbol}", response_model=SymbolOut, dependencies=[Depends(require_csrf)])
async def update_symbol(
    symbol: str,
    payload: SymbolUpdateRequest,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> SymbolOut:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    result = await session.execute(select(Symbol).where(Symbol.symbol == symbol.upper()))
    sym = result.scalar_one_or_none()
    if sym is None:
        raise HTTPException(status_code=404, detail="Sembol bulunamadi")

    rule = await get_or_create_symbol_rule(session, admin.id, symbol.upper())
    before = {c.name: str(getattr(rule, c.name)) for c in rule.__table__.columns}

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(rule, field, value)

    await session.commit()
    await session.refresh(rule)

    after = {c.name: str(getattr(rule, c.name)) for c in rule.__table__.columns}
    await record_audit_log(
        session, admin_id=admin.id, action="UPDATE_SYMBOL_RULE", entity_type="symbol_rule", entity_id=symbol.upper(),
        before_data=before, after_data=after,
    )

    return _to_symbol_out(sym, rule, settings_row.leverage)
