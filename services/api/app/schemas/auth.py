from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from shared.enums import ApprovalStatus, UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class AdminOut(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    phone: str | None = None
    city: str | None = None
    district: str | None = None
    last_login_at: datetime | None = None
    firebase_uid: str | None = None
    role: UserRole = UserRole.CUSTOMER
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    is_active: bool = True
    membership_plan: str | None = None
    membership_starts_at: datetime | None = None
    membership_expires_at: datetime | None = None
    membership_days_remaining: int | None = None
    membership_active: bool | None = None

    class Config:
        from_attributes = True


class FirebaseLoginRequest(BaseModel):
    id_token: str = Field(min_length=10)


class CustomerRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=256)
    full_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=10, max_length=32)
    city: str = Field(min_length=2, max_length=64)
    district: str = Field(min_length=2, max_length=64)


class LoginResponse(BaseModel):
    admin: AdminOut
    csrf_token: str
    auth_provider: str = "local"
