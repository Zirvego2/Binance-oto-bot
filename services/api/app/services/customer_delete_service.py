"""Platform admin: musteri hesabini ve tum tenant verisini kalici silme."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import (
    Admin,
    AdminProfile,
    AdminSession,
    AlgoOrder,
    AnalysisResult,
    AuditLog,
    BinanceConnectionStatus,
    BotEvent,
    BotRuntimeStatus,
    BotSettings,
    DailyStatistic,
    FundTransferLog,
    FundingRecord,
    Order,
    OrderFill,
    PnlRecord,
    Position,
    StrategySignal,
    SymbolRule,
    TelegramDeliveryLog,
    Trade,
)
from shared.db.models_enhanced import AiExplanation
from shared.enums import UserRole

from ..core.binance_client import invalidate_binance_adapter_cache
from ..core.firebase import firebase_enabled
from ..schemas.platform_admin import CustomerDeleteOut
from .audit_service import record_audit_log

logger = logging.getLogger(__name__)


async def _purge_firestore_customer(firebase_uid: str | None, admin_id: str) -> None:
    if not firebase_enabled():
        return
    try:
        from shared.firestore.tenant_repository import delete_customer_firestore_data

        await delete_customer_firestore_data(firebase_uid, admin_id)
    except Exception:
        logger.warning("Firestore musteri silme basarisiz (admin=%s)", admin_id, exc_info=True)


async def delete_customer_for_platform(
    session: AsyncSession,
    customer_id: str,
    *,
    platform_admin: Admin,
    ip_address: str | None = None,
) -> CustomerDeleteOut:
    customer = (
        await session.execute(
            select(Admin).where(Admin.id == customer_id, Admin.role == UserRole.CUSTOMER.value)
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")

    if platform_admin.id == customer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kendi hesabinizi silemezsiniz")

    email = customer.email
    firebase_uid = customer.firebase_uid

    position_ids = list(
        (await session.execute(select(Position.id).where(Position.admin_id == customer_id))).scalars().all()
    )
    order_ids = list(
        (await session.execute(select(Order.id).where(Order.admin_id == customer_id))).scalars().all()
    )
    signal_ids = list(
        (await session.execute(select(StrategySignal.id).where(StrategySignal.admin_id == customer_id))).scalars().all()
    )

    await record_audit_log(
        session,
        admin_id=platform_admin.id,
        action="DELETE_CUSTOMER",
        entity_type="customer",
        entity_id=customer_id,
        before_data={
            "email": email,
            "full_name": customer.full_name,
            "approval_status": customer.approval_status,
            "firebase_uid": firebase_uid,
            "open_positions": len(position_ids),
            "trades_hint": "all tenant data removed",
        },
        ip_address=ip_address,
    )

    if order_ids:
        await session.execute(delete(OrderFill).where(OrderFill.order_id.in_(order_ids)))

    await session.execute(delete(AlgoOrder).where(AlgoOrder.admin_id == customer_id))
    await session.execute(delete(Trade).where(Trade.admin_id == customer_id))

    if position_ids:
        await session.execute(delete(PnlRecord).where(PnlRecord.position_id.in_(position_ids)))
        await session.execute(delete(FundingRecord).where(FundingRecord.position_id.in_(position_ids)))

    await session.execute(delete(Order).where(Order.admin_id == customer_id))
    await session.execute(delete(Position).where(Position.admin_id == customer_id))

    if signal_ids:
        await session.execute(delete(AiExplanation).where(AiExplanation.signal_id.in_(signal_ids)))

    await session.execute(delete(AnalysisResult).where(AnalysisResult.admin_id == customer_id))
    await session.execute(delete(StrategySignal).where(StrategySignal.admin_id == customer_id))
    await session.execute(delete(DailyStatistic).where(DailyStatistic.admin_id == customer_id))
    await session.execute(delete(SymbolRule).where(SymbolRule.admin_id == customer_id))
    await session.execute(delete(BotEvent).where(BotEvent.admin_id == customer_id))
    await session.execute(delete(TelegramDeliveryLog).where(TelegramDeliveryLog.admin_id == customer_id))
    await session.execute(delete(AdminSession).where(AdminSession.admin_id == customer_id))
    await session.execute(delete(FundTransferLog).where(FundTransferLog.customer_id == customer_id))
    await session.execute(delete(AdminProfile).where(AdminProfile.admin_id == customer_id))
    await session.execute(delete(BotSettings).where(BotSettings.admin_id == customer_id))
    await session.execute(delete(BotRuntimeStatus).where(BotRuntimeStatus.admin_id == customer_id))
    await session.execute(delete(BinanceConnectionStatus).where(BinanceConnectionStatus.admin_id == customer_id))
    await session.execute(delete(AuditLog).where(AuditLog.admin_id == customer_id))
    await session.execute(delete(AuditLog).where(AuditLog.entity_id == customer_id))

    await session.delete(customer)
    await session.commit()

    invalidate_binance_adapter_cache(customer_id)
    await _purge_firestore_customer(firebase_uid, customer_id)

    return CustomerDeleteOut(
        ok=True,
        customer_id=customer_id,
        email=email,
        message=f"{email} ve tum tenant verisi kalici olarak silindi",
    )
