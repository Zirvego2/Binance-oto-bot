from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin

from ...core.config import Settings, get_settings
from ...core.database import get_db
from ...core.rate_limit import RateLimitExceeded, enforce_rate_limit
from ...core.security import generate_csrf_token
from ...schemas.auth import AdminOut, CustomerRegisterRequest, FirebaseLoginRequest, LoginRequest, LoginResponse
from ...schemas.platform_admin import CustomerRegisterPendingOut
from ...services.audit_service import record_audit_log
from ...services.auth_presenter import admin_to_out
from ...services.auth_service import authenticate_admin, revoke_session
from ...services.firebase_auth_service import (
    authenticate_customer_with_password,
    authenticate_with_firebase_token,
    register_customer,
)
from ..deps import get_current_admin, get_redis_dep

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis_dep),
) -> LoginResponse:
    client_ip = request.client.host if request.client else "unknown"

    try:
        await enforce_rate_limit(redis, f"ratelimit:login:ip:{client_ip}", max_requests=10, window_seconds=60)
        await enforce_rate_limit(
            redis, f"ratelimit:login:email:{payload.email.lower()}", max_requests=8, window_seconds=300
        )
    except RateLimitExceeded as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Cok fazla giris denemesi. Lutfen daha sonra tekrar deneyin.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    admin, token = await authenticate_admin(
        session,
        payload.email,
        payload.password,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )

    await record_audit_log(session, admin_id=admin.id, action="LOGIN", entity_type="admin", entity_id=admin.id, ip_address=client_ip)

    csrf_token = _set_session_cookies(response, settings, token)
    return LoginResponse(admin=admin_to_out(admin), csrf_token=csrf_token, auth_provider="local")


def _set_session_cookies(response: Response, settings: Settings, token: str) -> str:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.session_ttl_minutes * 60,
        path="/",
    )
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.session_ttl_minutes * 60,
        path="/",
    )
    return csrf_token


@router.post("/firebase-login", response_model=LoginResponse)
async def firebase_login(
    payload: FirebaseLoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis_dep),
) -> LoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    try:
        await enforce_rate_limit(redis, f"ratelimit:firebase-login:ip:{client_ip}", max_requests=20, window_seconds=60)
    except RateLimitExceeded as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Cok fazla giris denemesi. Lutfen daha sonra tekrar deneyin.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    admin, token = await authenticate_with_firebase_token(
        session,
        payload.id_token,
        settings,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    await record_audit_log(
        session,
        admin_id=admin.id,
        action="FIREBASE_LOGIN",
        entity_type="admin",
        entity_id=admin.id,
        ip_address=client_ip,
    )
    csrf_token = _set_session_cookies(response, settings, token)
    return LoginResponse(admin=admin_to_out(admin), csrf_token=csrf_token, auth_provider="firebase")


@router.post("/customer-login", response_model=LoginResponse)
async def customer_login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis_dep),
) -> LoginResponse:
    """Mevcut yerel hesap sifresi ile giris; Firebase kullanicisi otomatik olusturulur/baglanir."""
    client_ip = request.client.host if request.client else "unknown"
    try:
        await enforce_rate_limit(redis, f"ratelimit:customer-login:ip:{client_ip}", max_requests=15, window_seconds=60)
    except RateLimitExceeded as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Cok fazla giris denemesi. Lutfen daha sonra tekrar deneyin.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    admin, token = await authenticate_customer_with_password(
        session,
        payload.email,
        payload.password,
        settings,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    await record_audit_log(
        session,
        admin_id=admin.id,
        action="CUSTOMER_LOGIN",
        entity_type="admin",
        entity_id=admin.id,
        ip_address=client_ip,
    )
    csrf_token = _set_session_cookies(response, settings, token)
    return LoginResponse(admin=admin_to_out(admin), csrf_token=csrf_token, auth_provider="firebase")


@router.post("/customer-register", response_model=CustomerRegisterPendingOut)
async def customer_register(
    payload: CustomerRegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis_dep),
) -> CustomerRegisterPendingOut:
    client_ip = request.client.host if request.client else "unknown"
    try:
        await enforce_rate_limit(redis, f"ratelimit:customer-register:ip:{client_ip}", max_requests=10, window_seconds=300)
    except RateLimitExceeded as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Cok fazla kayit denemesi. Lutfen daha sonra tekrar deneyin.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    admin = await register_customer(
        session,
        payload.email,
        payload.password,
        settings,
        full_name=payload.full_name,
        phone=payload.phone,
        city=payload.city,
        district=payload.district,
    )
    await record_audit_log(
        session,
        admin_id=admin.id,
        action="CUSTOMER_REGISTER",
        entity_type="admin",
        entity_id=admin.id,
        ip_address=client_ip,
    )
    return CustomerRegisterPendingOut(
        email=admin.email,
        message="Kayit alindi. Hesabiniz yonetici onayindan sonra aktif olacaktir.",
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await revoke_session(session, token)
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie("csrf_token", path="/")
    return {"ok": True}


@router.get("/me", response_model=AdminOut)
async def me(admin: Admin = Depends(get_current_admin)) -> AdminOut:
    return admin_to_out(admin)
