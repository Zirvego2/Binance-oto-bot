"""Admin panelinden musteri bakiyelerini TRC20 ile toplama servisi."""

from __future__ import annotations

import asyncio
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.errors import BinanceApiError
from shared.binance.spot_client import BinanceSpotClient
from shared.db import Admin, BotSettings, FundTransferLog, Position
from shared.db.models_profile import AdminProfile
from shared.enums import ApprovalStatus, UserRole
from shared.decimal_utils import to_decimal

from ..core.binance_client import get_binance_adapter_for_admin, resolve_binance_credentials_for_admin
from ..core.config import Settings, get_settings
from ..schemas.platform_admin import (
    FundTransferExecuteOut,
    FundTransferHistoryOut,
    FundTransferPreviewOut,
    WithdrawableCustomerOut,
)
from .audit_service import record_audit_log

ZERO = Decimal("0")
CHECK_CONCURRENCY = 5


def _settings() -> Settings:
    return get_settings()


async def _spot_client_for_customer(session: AsyncSession, customer_id: str) -> BinanceSpotClient | None:
    creds = await resolve_binance_credentials_for_admin(session, customer_id)
    if not creds or not creds.api_key or not creds.api_secret:
        return None
    settings = _settings()
    client = BinanceSpotClient(
        base_url=settings.binance_spot_base_url,
        api_key=creds.api_key,
        api_secret=creds.api_secret,
    )
    await client.sync_server_time()
    return client


async def _open_positions_count(session: AsyncSession, customer_id: str) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Position)
                .where(Position.admin_id == customer_id, Position.status == "OPEN")
            )
        ).scalar_one()
    )


async def _inspect_customer_withdrawability(
    session: AsyncSession,
    customer: Admin,
    profile: AdminProfile | None,
    settings_row: BotSettings | None,
    *,
    destination_address: str,
    network: str,
) -> WithdrawableCustomerOut:
    has_binance = bool(profile and profile.binance_api_key_enc)
    mode = settings_row.mode if settings_row else "paper"
    open_positions = await _open_positions_count(session, customer.id)

    base = WithdrawableCustomerOut(
        customer_id=customer.id,
        email=customer.email,
        full_name=customer.full_name,
        bot_mode=mode,
        has_binance=has_binance,
        open_positions_count=open_positions,
        ip_restrict=False,
        withdraw_enabled=False,
        eligible=False,
        futures_available_usdt=ZERO,
        spot_usdt_balance=ZERO,
        estimated_withdraw_usdt=ZERO,
        withdraw_fee_usdt=ZERO,
        destination_address=destination_address,
        network=network,
    )

    if not has_binance:
        base.ineligible_reason = "Binance API tanimli degil"
        return base
    if mode != "live":
        base.ineligible_reason = "Yalnizca live mod musterileri desteklenir"
        return base
    if customer.approval_status != ApprovalStatus.APPROVED.value:
        base.ineligible_reason = "Musteri onayli degil"
        return base
    if open_positions > 0:
        base.ineligible_reason = f"{open_positions} acik pozisyon var"
        return base

    spot_client = await _spot_client_for_customer(session, customer.id)
    if spot_client is None:
        base.ineligible_reason = "Binance API cozulemedi"
        return base

    try:
        restrictions = await spot_client.get_api_restrictions()
        base.ip_restrict = restrictions.ip_restrict
        base.withdraw_enabled = restrictions.enable_withdrawals

        if not restrictions.ip_restrict:
            base.ineligible_reason = "API anahtarinda IP kisitlamasi yok"
            return base
        if not restrictions.enable_withdrawals:
            base.ineligible_reason = "API anahtarinda withdraw izni kapali"
            return base
        if not restrictions.enable_internal_transfer:
            base.ineligible_reason = "API anahtarinda ic transfer izni kapali"
            return base

        adapter = await get_binance_adapter_for_admin(session, customer.id, "live")
        account = await adapter.get_account_info()
        base.futures_available_usdt = account.available_balance
        base.spot_usdt_balance = await spot_client.get_asset_balance("USDT")

        network_cfg = await spot_client.get_coin_network_config("USDT", network)
        if network_cfg is None:
            base.ineligible_reason = f"{network} agi bulunamadi"
            return base
        if not network_cfg.withdraw_enabled:
            base.ineligible_reason = f"{network} aginda cekim kapali"
            return base

        base.withdraw_fee_usdt = network_cfg.withdraw_fee
        total_available = base.futures_available_usdt + base.spot_usdt_balance
        base.estimated_withdraw_usdt = max(ZERO, total_available - network_cfg.withdraw_fee)

        min_usdt = to_decimal(_settings().fund_transfer_min_usdt)
        if base.estimated_withdraw_usdt < min_usdt:
            base.ineligible_reason = f"Minimum cekim tutari ({min_usdt} USDT) altinda"
            return base
        if total_available < network_cfg.withdraw_min:
            base.ineligible_reason = f"Binance minimum cekim ({network_cfg.withdraw_min} USDT) altinda"
            return base

        base.eligible = True
        base.ineligible_reason = None
        return base
    except BinanceApiError as exc:
        base.ineligible_reason = f"Binance: {exc.message}"
        return base
    except Exception as exc:
        base.ineligible_reason = str(exc)
        return base
    finally:
        await spot_client.close()


async def list_withdrawable_customers(session: AsyncSession) -> list[WithdrawableCustomerOut]:
    settings = _settings()
    destination = settings.admin_trc20_address.strip()
    network = settings.admin_trc20_network.strip().upper()
    if not destination:
        raise HTTPException(status_code=500, detail="Admin TRC20 adresi tanimli degil")

    customers = (
        await session.execute(
            select(Admin)
            .where(Admin.role == UserRole.CUSTOMER.value)
            .where(Admin.approval_status == ApprovalStatus.APPROVED.value)
            .order_by(Admin.email.asc())
        )
    ).scalars().all()
    if not customers:
        return []

    customer_ids = [c.id for c in customers]
    profiles = {
        row.admin_id: row
        for row in (
            await session.execute(select(AdminProfile).where(AdminProfile.admin_id.in_(customer_ids)))
        ).scalars().all()
    }
    settings_map = {
        row.admin_id: row
        for row in (
            await session.execute(
                select(BotSettings).where(BotSettings.admin_id.in_(customer_ids))
            )
        ).scalars().all()
        if row.admin_id
    }

    candidates = [
        c
        for c in customers
        if profiles.get(c.id) and profiles[c.id].binance_api_key_enc and settings_map.get(c.id) and settings_map[c.id].mode == "live"
    ]

    semaphore = asyncio.Semaphore(CHECK_CONCURRENCY)

    async def _check(customer: Admin) -> WithdrawableCustomerOut:
        async with semaphore:
            return await _inspect_customer_withdrawability(
                session,
                customer,
                profiles.get(customer.id),
                settings_map.get(customer.id),
                destination_address=destination,
                network=network,
            )

    results = await asyncio.gather(*[_check(c) for c in candidates])
    return sorted(results, key=lambda row: (not row.eligible, row.email.lower()))


async def get_fund_transfer_preview(session: AsyncSession, customer_id: str) -> FundTransferPreviewOut:
    customer = (
        await session.execute(
            select(Admin).where(Admin.id == customer_id, Admin.role == UserRole.CUSTOMER.value)
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Musteri bulunamadi")

    profile = (
        await session.execute(select(AdminProfile).where(AdminProfile.admin_id == customer_id))
    ).scalar_one_or_none()
    settings_row = (
        await session.execute(select(BotSettings).where(BotSettings.admin_id == customer_id))
    ).scalar_one_or_none()

    settings = _settings()
    row = await _inspect_customer_withdrawability(
        session,
        customer,
        profile,
        settings_row,
        destination_address=settings.admin_trc20_address.strip(),
        network=settings.admin_trc20_network.strip().upper(),
    )
    return FundTransferPreviewOut(**row.model_dump())


async def execute_fund_transfer(
    session: AsyncSession,
    customer_id: str,
    *,
    platform_admin: Admin,
    ip_address: str | None = None,
) -> FundTransferExecuteOut:
    preview = await get_fund_transfer_preview(session, customer_id)
    if not preview.eligible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=preview.ineligible_reason or "Musteri transfer icin uygun degil",
        )

    settings = _settings()
    destination = settings.admin_trc20_address.strip()
    network = settings.admin_trc20_network.strip().upper()
    spot_client = await _spot_client_for_customer(session, customer_id)
    if spot_client is None:
        raise HTTPException(status_code=400, detail="Binance API cozulemedi")

    log = FundTransferLog(
        customer_id=customer_id,
        platform_admin_id=platform_admin.id,
        amount_usdt=ZERO,
        destination_address=destination,
        network=network,
        status="pending",
    )
    session.add(log)
    await session.flush()

    try:
        adapter = await get_binance_adapter_for_admin(session, customer_id, "live")
        account = await adapter.get_account_info()
        futures_available = account.available_balance
        spot_before = await spot_client.get_asset_balance("USDT")

        transferred = ZERO
        if futures_available > ZERO:
            await spot_client.transfer_futures_to_spot("USDT", futures_available)
            transferred = futures_available
            await asyncio.sleep(1.5)

        spot_after = await spot_client.get_asset_balance("USDT")
        network_cfg = await spot_client.get_coin_network_config("USDT", network)
        if network_cfg is None:
            raise HTTPException(status_code=400, detail=f"{network} agi bulunamadi")

        withdraw_amount = spot_after - network_cfg.withdraw_fee
        if withdraw_amount < network_cfg.withdraw_min:
            raise HTTPException(
                status_code=400,
                detail=f"Cekilebilir tutar minimumun altinda ({network_cfg.withdraw_min} USDT)",
            )

        withdraw_result = await spot_client.withdraw(
            coin="USDT",
            address=destination,
            amount=withdraw_amount,
            network=network,
            withdraw_order_id=log.id.replace("-", ""),
        )

        log.futures_transferred_usdt = transferred
        log.spot_balance_before_usdt = spot_before
        log.withdraw_fee_usdt = network_cfg.withdraw_fee
        log.amount_usdt = withdraw_amount
        log.binance_withdraw_id = str(withdraw_result.get("id", ""))
        log.status = "success"
        await session.commit()

        await record_audit_log(
            session,
            admin_id=platform_admin.id,
            action="FUND_TRANSFER_TRC20",
            entity_type="customer",
            entity_id=customer_id,
            after_data={
                "amount_usdt": str(withdraw_amount),
                "destination_address": destination,
                "network": network,
                "binance_withdraw_id": log.binance_withdraw_id,
                "customer_email": preview.email,
            },
            ip_address=ip_address,
        )

        return FundTransferExecuteOut(
            ok=True,
            transfer_id=log.id,
            amount_usdt=withdraw_amount,
            withdraw_fee_usdt=network_cfg.withdraw_fee,
            futures_transferred_usdt=transferred,
            binance_withdraw_id=log.binance_withdraw_id,
            destination_address=destination,
            network=network,
            message="TRC20 transferi baslatildi",
        )
    except HTTPException as exc:
        log.status = "failed"
        log.error_message = str(exc.detail)
        await session.commit()
        raise
    except BinanceApiError as exc:
        log.status = "failed"
        log.error_message = exc.message
        await session.commit()
        raise HTTPException(status_code=400, detail=f"Binance hatasi: {exc.message}") from exc
    except Exception as exc:
        log.status = "failed"
        log.error_message = str(exc)
        await session.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await spot_client.close()


async def list_fund_transfer_history(session: AsyncSession, *, limit: int = 50) -> list[FundTransferHistoryOut]:
    limit = min(max(1, limit), 100)
    rows = (
        await session.execute(
            select(FundTransferLog).order_by(FundTransferLog.created_at.desc()).limit(limit)
        )
    ).scalars().all()

    customer_ids = {row.customer_id for row in rows}
    admin_ids = {row.platform_admin_id for row in rows}
    email_map: dict[str, str] = {}
    if customer_ids or admin_ids:
        ids = list(customer_ids | admin_ids)
        admins = (await session.execute(select(Admin.id, Admin.email).where(Admin.id.in_(ids)))).all()
        email_map = {admin_id: email for admin_id, email in admins}

    return [
        FundTransferHistoryOut(
            id=row.id,
            customer_id=row.customer_id,
            customer_email=email_map.get(row.customer_id),
            platform_admin_email=email_map.get(row.platform_admin_id),
            amount_usdt=row.amount_usdt,
            withdraw_fee_usdt=row.withdraw_fee_usdt,
            futures_transferred_usdt=row.futures_transferred_usdt,
            destination_address=row.destination_address,
            network=row.network,
            binance_withdraw_id=row.binance_withdraw_id,
            status=row.status,
            error_message=row.error_message,
            created_at=row.created_at,
        )
        for row in rows
    ]
