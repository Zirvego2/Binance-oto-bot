"""Platform yonetici API rotalari."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin
from shared.enums import ApprovalStatus

from ...core.database import get_db
from ...schemas.common import PaginatedResponse
from ...schemas.platform_admin import (
    AdminTradeOut,
    CustomerApprovalUpdate,
    CustomerDeleteOut,
    CustomerDetailOut,
    CustomerEarningsDetailOut,
    CustomerListItemOut,
    FundTransferExecuteOut,
    FundTransferHistoryOut,
    FundTransferPreviewOut,
    MembershipExtendUpdate,
    MembershipOverviewOut,
    MembershipPlanOut,
    PlatformActivityOut,
    PlatformEarningsSummaryOut,
    PlatformOverviewOut,
    WithdrawableCustomerOut,
)
from ...schemas.trading import PositionOut
from ..deps import require_csrf, require_platform_admin
from ...services.admin_fund_transfer_service import (
    execute_fund_transfer,
    get_fund_transfer_preview,
    list_fund_transfer_history,
    list_withdrawable_customers,
)
from ...services.customer_delete_service import delete_customer_for_platform
from ...services.customer_earnings_service import get_customer_earnings_detail, get_customer_earnings_report
from ...services.platform_admin_service import (
    extend_customer_membership,
    get_customer_detail,
    get_membership_overview,
    get_platform_activity,
    get_platform_overview,
    list_customers_paginated,
    update_customer_approval,
)
from shared.membership import list_membership_plans
from ...services.platform_positions_service import list_customer_positions_for_platform
from ...services.platform_trades_service import list_platform_trades
from ...services.trades_service import delete_trade_for_platform

router = APIRouter(prefix="/platform", tags=["platform-admin"])


@router.get("/overview", response_model=PlatformOverviewOut)
async def platform_overview(
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> PlatformOverviewOut:
    return await get_platform_overview(session)


@router.get("/activity", response_model=list[PlatformActivityOut])
async def platform_activity(
    limit: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> list[PlatformActivityOut]:
    return await get_platform_activity(session, limit=limit)


@router.get("/customers", response_model=PaginatedResponse[CustomerListItemOut])
async def platform_customers(
    approval_status: ApprovalStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=255),
    membership_filter: str | None = Query(default=None, pattern="^(all|active|expiring|expired|none)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> PaginatedResponse[CustomerListItemOut]:
    return await list_customers_paginated(
        session,
        approval_status=approval_status,
        search=search,
        membership_filter=membership_filter,
        page=page,
        page_size=page_size,
    )


@router.get("/customers/{customer_id}", response_model=CustomerDetailOut)
async def platform_customer_detail(
    customer_id: str,
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> CustomerDetailOut:
    return await get_customer_detail(session, customer_id)


@router.delete(
    "/customers/{customer_id}",
    response_model=CustomerDeleteOut,
    dependencies=[Depends(require_csrf)],
)
async def platform_delete_customer(
    customer_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(require_platform_admin),
) -> CustomerDeleteOut:
    client_ip = request.client.host if request.client else None
    return await delete_customer_for_platform(
        session,
        customer_id,
        platform_admin=admin,
        ip_address=client_ip,
    )


@router.get("/customer-earnings", response_model=PlatformEarningsSummaryOut)
async def platform_customer_earnings(
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> PlatformEarningsSummaryOut:
    return await get_customer_earnings_report(session)


@router.get("/customer-earnings/{customer_id}", response_model=CustomerEarningsDetailOut)
async def platform_customer_earnings_detail(
    customer_id: str,
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> CustomerEarningsDetailOut:
    return await get_customer_earnings_detail(session, customer_id)


@router.get("/customers/{customer_id}/positions", response_model=PaginatedResponse[PositionOut])
async def platform_customer_positions(
    customer_id: str,
    status_filter: str | None = Query(default=None, pattern="^(OPEN|CLOSED)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> PaginatedResponse[PositionOut]:
    return await list_customer_positions_for_platform(
        session,
        customer_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )


@router.get("/trades", response_model=PaginatedResponse[AdminTradeOut])
async def platform_trades(
    symbol: str | None = Query(default=None, max_length=32),
    side: str | None = Query(default=None, max_length=8),
    bot_mode: str | None = Query(default=None, max_length=16),
    customer_id: str | None = Query(default=None, max_length=36),
    search: str | None = Query(default=None, max_length=255),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    sort_by: str = Query(default="closed_at", max_length=32),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> PaginatedResponse[AdminTradeOut]:
    return await list_platform_trades(
        session,
        symbol=symbol,
        side=side,
        bot_mode=bot_mode,
        customer_id=customer_id,
        search=search,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/trades/{trade_id}",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(require_csrf)],
)
async def platform_delete_trade(
    trade_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(require_platform_admin),
) -> Response:
    client_ip = request.client.host if request.client else None
    deleted = await delete_trade_for_platform(
        session,
        trade_id,
        acting_admin_id=admin.id,
        ip_address=client_ip,
    )
    if deleted is None:
        raise HTTPException(status_code=404, detail="Islem bulunamadi")
    return Response(status_code=204)


@router.get("/membership-plans", response_model=list[MembershipPlanOut])
async def platform_membership_plans(
    _admin: Admin = Depends(require_platform_admin),
) -> list[MembershipPlanOut]:
    return [MembershipPlanOut(**plan) for plan in list_membership_plans()]


@router.get("/memberships/overview", response_model=MembershipOverviewOut)
async def platform_memberships_overview(
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> MembershipOverviewOut:
    return await get_membership_overview(session)


@router.patch(
    "/customers/{customer_id}/membership",
    response_model=CustomerDetailOut,
    dependencies=[Depends(require_csrf)],
)
async def platform_extend_customer_membership(
    customer_id: str,
    payload: MembershipExtendUpdate,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(require_platform_admin),
) -> CustomerDetailOut:
    return await extend_customer_membership(session, customer_id, payload, platform_admin=admin)


@router.patch("/customers/{customer_id}/approval", response_model=CustomerDetailOut, dependencies=[Depends(require_csrf)])
async def platform_customer_approval(
    customer_id: str,
    payload: CustomerApprovalUpdate,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(require_platform_admin),
) -> CustomerDetailOut:
    return await update_customer_approval(session, customer_id, payload, platform_admin=admin)


@router.get("/fund-transfers/eligible", response_model=list[WithdrawableCustomerOut])
async def platform_fund_transfers_eligible(
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> list[WithdrawableCustomerOut]:
    return await list_withdrawable_customers(session)


@router.get("/fund-transfers/preview/{customer_id}", response_model=FundTransferPreviewOut)
async def platform_fund_transfer_preview(
    customer_id: str,
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> FundTransferPreviewOut:
    return await get_fund_transfer_preview(session, customer_id)


@router.post(
    "/fund-transfers/{customer_id}/execute",
    response_model=FundTransferExecuteOut,
    dependencies=[Depends(require_csrf)],
)
async def platform_fund_transfer_execute(
    customer_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(require_platform_admin),
) -> FundTransferExecuteOut:
    client_ip = request.client.host if request.client else None
    return await execute_fund_transfer(
        session,
        customer_id,
        platform_admin=admin,
        ip_address=client_ip,
    )


@router.get("/fund-transfers/history", response_model=list[FundTransferHistoryOut])
async def platform_fund_transfer_history(
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _admin: Admin = Depends(require_platform_admin),
) -> list[FundTransferHistoryOut]:
    return await list_fund_transfer_history(session, limit=limit)
