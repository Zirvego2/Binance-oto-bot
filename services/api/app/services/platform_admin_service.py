"""Platform yonetici paneli servisleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, AdminSession, AuditLog, BotRuntimeStatus, BotSettings, Position
from shared.db.models_profile import AdminProfile
from shared.enums import ApprovalStatus, UserRole
from shared.membership import (
    extend_membership,
    grant_membership,
    is_membership_active,
    list_membership_plans,
    membership_days_remaining,
)
from shared.timezone_utils import local_now

from ..core.firebase import firebase_enabled
from ..schemas.common import PaginatedResponse
from ..schemas.platform_admin import (
    CustomerApprovalUpdate,
    CustomerDetailOut,
    CustomerListItemOut,
    MembershipExtendUpdate,
    MembershipOverviewOut,
    MembershipPlanOut,
    PlatformActivityOut,
    PlatformOverviewOut,
    RegistrationDayOut,
    PLATFORM_CUSTOMER_CAPACITY,
)
from .firestore_customer_service import get_customer, upsert_customer
from shared.tenant_settings import provision_tenant_defaults


def _is_online(last_login_at: datetime | None) -> bool:
    if last_login_at is None:
        return False
    login = last_login_at.replace(tzinfo=timezone.utc) if last_login_at.tzinfo is None else last_login_at
    return login >= datetime.now(timezone.utc) - timedelta(minutes=15)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _active_session_counts(session: AsyncSession) -> dict[str, int]:
    now = _utc_now()
    rows = (
        await session.execute(
            select(AdminSession.admin_id, func.count())
            .where(AdminSession.revoked_at.is_(None))
            .where(AdminSession.expires_at > now)
            .group_by(AdminSession.admin_id)
        )
    ).all()
    return {admin_id: int(count) for admin_id, count in rows}


async def _profile_flags(session: AsyncSession, admin_ids: list[str]) -> dict[str, AdminProfile]:
    if not admin_ids:
        return {}
    rows = (await session.execute(select(AdminProfile).where(AdminProfile.admin_id.in_(admin_ids)))).scalars().all()
    return {row.admin_id: row for row in rows}


async def _open_position_counts(session: AsyncSession, admin_ids: list[str] | None = None) -> dict[str, int]:
    query = (
        select(Position.admin_id, func.count())
        .where(Position.status == "OPEN", Position.admin_id.is_not(None))
        .group_by(Position.admin_id)
    )
    if admin_ids:
        query = query.where(Position.admin_id.in_(admin_ids))
    rows = (await session.execute(query)).all()
    return {admin_id: int(count) for admin_id, count in rows if admin_id}


async def _runtime_by_admin(session: AsyncSession, admin_ids: list[str] | None = None) -> dict[str, BotRuntimeStatus]:
    query = select(BotRuntimeStatus).where(BotRuntimeStatus.admin_id.is_not(None))
    if admin_ids:
        query = query.where(BotRuntimeStatus.admin_id.in_(admin_ids))
    rows = (await session.execute(query)).scalars().all()
    return {row.admin_id: row for row in rows if row.admin_id}


async def _settings_by_admin(session: AsyncSession, admin_ids: list[str] | None = None) -> dict[str, BotSettings]:
    query = select(BotSettings).where(BotSettings.admin_id.is_not(None))
    if admin_ids:
        query = query.where(BotSettings.admin_id.in_(admin_ids))
    rows = (await session.execute(query)).scalars().all()
    return {row.admin_id: row for row in rows if row.admin_id}


def _registration_trend(customers: list[Admin], days: int = 7) -> list[RegistrationDayOut]:
    now_local = local_now()
    buckets: dict[str, int] = {}
    for offset in range(days - 1, -1, -1):
        day = (now_local - timedelta(days=offset)).date().isoformat()
        buckets[day] = 0
    for customer in customers:
        if not customer.created_at:
            continue
        created = customer.created_at.replace(tzinfo=timezone.utc) if customer.created_at.tzinfo is None else customer.created_at
        day_key = local_now(created).date().isoformat()
        if day_key in buckets:
            buckets[day_key] += 1
    return [RegistrationDayOut(date=day, count=count) for day, count in buckets.items()]


async def get_platform_overview(session: AsyncSession) -> PlatformOverviewOut:
    customers = (
        await session.execute(select(Admin).where(Admin.role == UserRole.CUSTOMER.value))
    ).scalars().all()
    session_counts = await _active_session_counts(session)
    profiles = await _profile_flags(session, [c.id for c in customers])
    position_counts = await _open_position_counts(session)
    runtimes = await _runtime_by_admin(session)

    now = _utc_now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    pending = approved = blocked = with_binance = with_telegram = with_openai = online = bot_running = new_7d = new_30d = trading_ready = 0
    total_open_positions = sum(position_counts.values())

    for customer in customers:
        profile = profiles.get(customer.id)
        created = customer.created_at
        if created:
            created_utc = created.replace(tzinfo=timezone.utc) if created.tzinfo is None else created
            if created_utc >= week_ago:
                new_7d += 1
            if created_utc >= month_ago:
                new_30d += 1

        if customer.approval_status == ApprovalStatus.PENDING.value:
            pending += 1
        elif customer.approval_status == ApprovalStatus.APPROVED.value:
            approved += 1
        elif customer.approval_status == ApprovalStatus.BLOCKED.value:
            blocked += 1

        has_binance = bool(profile and profile.binance_api_key_enc)
        if has_binance:
            with_binance += 1
        if profile and profile.telegram_bot_token_enc:
            with_telegram += 1
        if profile and profile.openai_api_key_enc:
            with_openai += 1
        if customer.approval_status == ApprovalStatus.APPROVED.value and has_binance:
            trading_ready += 1

        if _is_online(customer.last_login_at) or session_counts.get(customer.id, 0) > 0:
            online += 1

        runtime = runtimes.get(customer.id)
        if runtime and runtime.run_state == "RUNNING":
            bot_running += 1

    return PlatformOverviewOut(
        total_customers=len(customers),
        pending_customers=pending,
        approved_customers=approved,
        blocked_customers=blocked,
        active_sessions=sum(session_counts.values()),
        customers_with_binance=with_binance,
        customers_with_telegram=with_telegram,
        customers_with_openai=with_openai,
        customers_online=online,
        customers_bot_running=bot_running,
        new_customers_7d=new_7d,
        new_customers_30d=new_30d,
        total_open_positions=total_open_positions,
        trading_ready_customers=trading_ready,
        platform_capacity=PLATFORM_CUSTOMER_CAPACITY,
        registration_trend_7d=_registration_trend(customers),
    )


def _customer_to_list_item(
    admin: Admin,
    *,
    profile: AdminProfile | None,
    active_sessions: int,
    open_positions_count: int,
    runtime: BotRuntimeStatus | None,
    settings: BotSettings | None,
) -> CustomerListItemOut:
    return CustomerListItemOut(
        id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
        phone=admin.phone,
        city=admin.city,
        district=admin.district,
        role=UserRole(admin.role),
        approval_status=ApprovalStatus(admin.approval_status),
        is_active=admin.is_active,
        firebase_uid=admin.firebase_uid,
        last_login_at=admin.last_login_at,
        last_login_ip=admin.last_login_ip,
        created_at=admin.created_at,
        approved_at=admin.approved_at,
        membership_plan=admin.membership_plan,
        membership_starts_at=admin.membership_starts_at,
        membership_expires_at=admin.membership_expires_at,
        membership_days_remaining=membership_days_remaining(admin),
        membership_active=is_membership_active(admin),
        has_binance=bool(profile and profile.binance_api_key_enc),
        has_telegram=bool(profile and profile.telegram_bot_token_enc),
        has_openai=bool(profile and profile.openai_api_key_enc),
        is_online=_is_online(admin.last_login_at) or active_sessions > 0,
        active_session_count=active_sessions,
        plan=None,
        blocked_reason=admin.blocked_reason,
        notes=admin.notes,
        open_positions_count=open_positions_count,
        bot_run_state=runtime.run_state if runtime else None,
        bot_enabled=bool(settings and settings.bot_enabled),
        bot_mode=settings.mode if settings else None,
    )


def _apply_membership_filter(query, membership_filter: str | None, *, now: datetime):
    if not membership_filter or membership_filter == "all":
        return query
    week_later = now + timedelta(days=7)
    expires = Admin.membership_expires_at
    if membership_filter == "active":
        return query.where(expires.isnot(None), expires > now)
    if membership_filter == "expiring":
        return query.where(expires.isnot(None), expires > now, expires <= week_later)
    if membership_filter == "expired":
        return query.where(expires.isnot(None), expires <= now)
    if membership_filter == "none":
        return query.where(expires.is_(None))
    return query


async def get_membership_overview(session: AsyncSession) -> MembershipOverviewOut:
    now = _utc_now()
    week_later = now + timedelta(days=7)
    customers = (
        await session.execute(select(Admin).where(Admin.role == UserRole.CUSTOMER.value))
    ).scalars().all()

    active = expiring = expired = no_membership = 0
    for customer in customers:
        expires = customer.membership_expires_at
        if expires is None:
            no_membership += 1
            continue
        expires_utc = expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires
        if expires_utc <= now:
            expired += 1
        elif expires_utc <= week_later:
            expiring += 1
        else:
            active += 1

    return MembershipOverviewOut(
        total_customers=len(customers),
        active_count=active,
        expiring_7d_count=expiring,
        expired_count=expired,
        no_membership_count=no_membership,
        plans=[MembershipPlanOut(**plan) for plan in list_membership_plans()],
    )


async def list_customers_paginated(
    session: AsyncSession,
    *,
    approval_status: ApprovalStatus | None = None,
    search: str | None = None,
    membership_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[CustomerListItemOut]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    now = _utc_now()

    base = select(Admin).where(Admin.role == UserRole.CUSTOMER.value)
    count_query = select(func.count()).select_from(Admin).where(Admin.role == UserRole.CUSTOMER.value)

    if approval_status is not None:
        base = base.where(Admin.approval_status == approval_status.value)
        count_query = count_query.where(Admin.approval_status == approval_status.value)
    if search:
        term = f"%{search.strip().lower()}%"
        filt = (Admin.email.ilike(term)) | (Admin.full_name.ilike(term))
        base = base.where(filt)
        count_query = count_query.where(filt)

    base = _apply_membership_filter(base, membership_filter, now=now)
    count_query = _apply_membership_filter(count_query, membership_filter, now=now)

    total = (await session.execute(count_query)).scalar_one()
    total_pages = max(1, (total + page_size - 1) // page_size)

    if membership_filter in ("expiring", "expired"):
        order = Admin.membership_expires_at.asc().nulls_last()
    elif membership_filter == "active":
        order = Admin.membership_expires_at.desc().nulls_last()
    else:
        order = Admin.created_at.desc()

    customers = (
        await session.execute(
            base.order_by(order).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    admin_ids = [c.id for c in customers]
    session_counts = await _active_session_counts(session)
    profiles = await _profile_flags(session, admin_ids)
    position_counts = await _open_position_counts(session, admin_ids)
    runtimes = await _runtime_by_admin(session, admin_ids)
    settings_map = await _settings_by_admin(session, admin_ids)

    items = [
        _customer_to_list_item(
            customer,
            profile=profiles.get(customer.id),
            active_sessions=session_counts.get(customer.id, 0),
            open_positions_count=position_counts.get(customer.id, 0),
            runtime=runtimes.get(customer.id),
            settings=settings_map.get(customer.id),
        )
        for customer in customers
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def list_customers(
    session: AsyncSession,
    *,
    approval_status: ApprovalStatus | None = None,
    search: str | None = None,
) -> list[CustomerListItemOut]:
    result = await list_customers_paginated(
        session,
        approval_status=approval_status,
        search=search,
        page=1,
        page_size=100,
    )
    return result.items


async def get_platform_activity(session: AsyncSession, *, limit: int = 30) -> list[PlatformActivityOut]:
    limit = min(max(1, limit), 100)
    rows = (
        await session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
    ).scalars().all()

    admin_ids = {row.admin_id for row in rows if row.admin_id}
    email_map: dict[str, str] = {}
    if admin_ids:
        admins = (
            await session.execute(select(Admin.id, Admin.email).where(Admin.id.in_(admin_ids)))
        ).all()
        email_map = {admin_id: email for admin_id, email in admins}

    return [
        PlatformActivityOut(
            id=row.id,
            action=row.action,
            entity_type=row.entity_type,
            customer_id=row.admin_id,
            customer_email=email_map.get(row.admin_id) if row.admin_id else None,
            created_at=row.created_at,
            ip_address=row.ip_address,
        )
        for row in rows
    ]


async def get_customer_detail(session: AsyncSession, customer_id: str) -> CustomerDetailOut:
    customer = (
        await session.execute(
            select(Admin).where(Admin.id == customer_id, Admin.role == UserRole.CUSTOMER.value)
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")

    session_counts = await _active_session_counts(session)
    profile = (
        await session.execute(select(AdminProfile).where(AdminProfile.admin_id == customer.id))
    ).scalar_one_or_none()
    position_counts = await _open_position_counts(session, [customer.id])
    runtime = (await _runtime_by_admin(session, [customer.id])).get(customer.id)
    settings = (await _settings_by_admin(session, [customer.id])).get(customer.id)

    firestore_doc = None
    if customer.firebase_uid and firebase_enabled():
        firestore_doc = await get_customer(customer.firebase_uid)

    base = _customer_to_list_item(
        customer,
        profile=profile,
        active_sessions=session_counts.get(customer.id, 0),
        open_positions_count=position_counts.get(customer.id, 0),
        runtime=runtime,
        settings=settings,
    )
    item = base.model_copy(update={"plan": (firestore_doc or {}).get("plan")})
    return CustomerDetailOut(
        **item.model_dump(),
        failed_login_count=customer.failed_login_count,
        locked_until=customer.locked_until,
        live_trading_ack_at=customer.live_trading_ack_at,
        firestore_synced=bool((firestore_doc or {}).get("dataInFirebase")),
        migration_mode=(firestore_doc or {}).get("migrationMode"),
    )


async def update_customer_approval(
    session: AsyncSession,
    customer_id: str,
    payload: CustomerApprovalUpdate,
    *,
    platform_admin: Admin,
) -> CustomerDetailOut:
    customer = (
        await session.execute(
            select(Admin).where(Admin.id == customer_id, Admin.role == UserRole.CUSTOMER.value)
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")

    customer.approval_status = payload.approval_status.value
    if payload.approval_status == ApprovalStatus.APPROVED:
        customer.approved_at = _utc_now()
        customer.approved_by_admin_id = platform_admin.id
        customer.blocked_reason = None
        if payload.is_active is None:
            customer.is_active = True
        if customer.membership_expires_at is None:
            grant_membership(
                customer,
                plan_id=payload.membership_plan_id,
            )
    elif payload.approval_status == ApprovalStatus.BLOCKED:
        customer.blocked_reason = payload.blocked_reason
        if payload.is_active is None:
            customer.is_active = False
    elif payload.approval_status == ApprovalStatus.PENDING:
        customer.approved_at = None
        customer.approved_by_admin_id = None

    if payload.notes is not None:
        customer.notes = payload.notes
    if payload.is_active is not None:
        customer.is_active = payload.is_active

    await session.commit()
    await session.refresh(customer)

    if payload.approval_status == ApprovalStatus.APPROVED:
        await provision_tenant_defaults(session, customer.id)
        await session.commit()

    if customer.firebase_uid and firebase_enabled():
        await upsert_customer(
            customer.firebase_uid,
            email=customer.email,
            admin_id=customer.id,
            full_name=customer.full_name,
            connections=None,
            approval_status=customer.approval_status,
        )

    return await get_customer_detail(session, customer_id)


async def extend_customer_membership(
    session: AsyncSession,
    customer_id: str,
    payload: MembershipExtendUpdate,
    *,
    platform_admin: Admin,
) -> CustomerDetailOut:
    customer = (
        await session.execute(
            select(Admin).where(Admin.id == customer_id, Admin.role == UserRole.CUSTOMER.value)
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")

    if payload.membership_plan_id is None and payload.duration_days is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paket veya gun sayisi belirtilmelidir",
        )

    old_expires = customer.membership_expires_at
    new_expires = extend_membership(
        customer,
        plan_id=payload.membership_plan_id,
        duration_days=payload.duration_days,
    )
    if customer.approval_status != ApprovalStatus.APPROVED.value:
        customer.approval_status = ApprovalStatus.APPROVED.value
        customer.approved_at = customer.approved_at or _utc_now()
        customer.approved_by_admin_id = customer.approved_by_admin_id or platform_admin.id
        customer.is_active = True

    if payload.note:
        note_line = f"[Uyelik uzatma {new_expires.date().isoformat()}] {payload.note.strip()}"
        customer.notes = f"{customer.notes}\n{note_line}".strip() if customer.notes else note_line

    await session.commit()
    await session.refresh(customer)

    from .audit_service import record_audit_log

    await record_audit_log(
        session,
        admin_id=platform_admin.id,
        action="EXTEND_MEMBERSHIP",
        entity_type="customer",
        entity_id=customer.id,
        before_data={"membership_expires_at": old_expires.isoformat() if old_expires else None},
        after_data={
            "membership_expires_at": new_expires.isoformat(),
            "membership_plan": customer.membership_plan,
            "note": payload.note,
        },
    )

    if customer.approval_status == ApprovalStatus.APPROVED.value:
        await provision_tenant_defaults(session, customer.id)
        await session.commit()

    if customer.firebase_uid and firebase_enabled():
        await upsert_customer(
            customer.firebase_uid,
            email=customer.email,
            admin_id=customer.id,
            full_name=customer.full_name,
            connections=None,
            approval_status=customer.approval_status,
        )

    return await get_customer_detail(session, customer_id)
