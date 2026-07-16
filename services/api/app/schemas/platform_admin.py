from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from shared.enums import ApprovalStatus, UserRole

from .trading import TradeOut


PLATFORM_CUSTOMER_CAPACITY = 100


class RegistrationDayOut(BaseModel):
    date: str
    count: int


class PlatformOverviewOut(BaseModel):
    total_customers: int
    pending_customers: int
    approved_customers: int
    blocked_customers: int
    active_sessions: int
    customers_with_binance: int
    customers_with_telegram: int
    customers_with_openai: int
    customers_online: int
    customers_bot_running: int
    new_customers_7d: int
    new_customers_30d: int
    total_open_positions: int
    trading_ready_customers: int
    platform_capacity: int = PLATFORM_CUSTOMER_CAPACITY
    registration_trend_7d: list[RegistrationDayOut] = Field(default_factory=list)


class CustomerListItemOut(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    phone: str | None = None
    city: str | None = None
    district: str | None = None
    role: UserRole
    approval_status: ApprovalStatus
    is_active: bool
    firebase_uid: str | None = None
    last_login_at: datetime | None = None
    last_login_ip: str | None = None
    created_at: datetime | None = None
    approved_at: datetime | None = None
    membership_plan: str | None = None
    membership_starts_at: datetime | None = None
    membership_expires_at: datetime | None = None
    membership_days_remaining: int | None = None
    membership_active: bool = True
    has_binance: bool = False
    has_telegram: bool = False
    has_openai: bool = False
    is_online: bool = False
    active_session_count: int = 0
    plan: str | None = None
    blocked_reason: str | None = None
    notes: str | None = None
    open_positions_count: int = 0
    bot_run_state: str | None = None
    bot_enabled: bool = False
    bot_mode: str | None = None


class CustomerDetailOut(CustomerListItemOut):
    failed_login_count: int = 0
    locked_until: datetime | None = None
    live_trading_ack_at: datetime | None = None
    firestore_synced: bool = False
    migration_mode: str | None = None


class CustomerApprovalUpdate(BaseModel):
    approval_status: ApprovalStatus
    blocked_reason: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None
    membership_plan_id: str | None = Field(default=None, max_length=32)


class MembershipPlanOut(BaseModel):
    id: str
    label: str
    duration_days: int
    price_usdt: int


class MembershipOverviewOut(BaseModel):
    total_customers: int
    active_count: int
    expiring_7d_count: int
    expired_count: int
    no_membership_count: int
    plans: list[MembershipPlanOut] = Field(default_factory=list)


class MembershipExtendUpdate(BaseModel):
    membership_plan_id: str | None = Field(default=None, max_length=32)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    note: str | None = Field(default=None, max_length=500)


class CustomerRegisterPendingOut(BaseModel):
    ok: bool = True
    message: str
    email: str


class CustomerEarningsPeriodOut(BaseModel):
    net_pnl_usdt: Decimal
    gross_pnl_usdt: Decimal
    trades_count: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal


class CustomerEarningsOut(BaseModel):
    customer_id: str
    email: str
    full_name: str | None = None
    approval_status: str
    daily: CustomerEarningsPeriodOut
    weekly: CustomerEarningsPeriodOut
    monthly: CustomerEarningsPeriodOut


class CustomerEarningsDetailOut(BaseModel):
    customer_id: str
    email: str
    full_name: str | None = None
    approval_status: str
    bot_mode: str | None = None
    bot_enabled: bool = False
    open_positions_count: int = 0
    total_unrealized_pnl_usdt: Decimal = Decimal("0")
    daily: CustomerEarningsPeriodOut
    weekly: CustomerEarningsPeriodOut
    monthly: CustomerEarningsPeriodOut
    lifetime: CustomerEarningsPeriodOut
    generated_at: datetime


class PlatformEarningsSummaryOut(BaseModel):
    daily_total_net_pnl_usdt: Decimal
    weekly_total_net_pnl_usdt: Decimal
    monthly_total_net_pnl_usdt: Decimal
    customer_count: int
    customers: list[CustomerEarningsOut]
    generated_at: datetime


class PlatformActivityOut(BaseModel):
    id: str
    action: str
    entity_type: str
    customer_id: str | None = None
    customer_email: str | None = None
    created_at: datetime
    ip_address: str | None = None


class AdminTradeOut(TradeOut):
    customer_id: str | None = None
    customer_email: str | None = None
    customer_full_name: str | None = None


class CustomerDeleteOut(BaseModel):
    ok: bool = True
    customer_id: str
    email: str
    message: str


class WithdrawableCustomerOut(BaseModel):
    customer_id: str
    email: str
    full_name: str | None = None
    bot_mode: str | None = None
    has_binance: bool = False
    open_positions_count: int = 0
    ip_restrict: bool = False
    withdraw_enabled: bool = False
    eligible: bool = False
    ineligible_reason: str | None = None
    futures_available_usdt: Decimal = Decimal("0")
    spot_usdt_balance: Decimal = Decimal("0")
    estimated_withdraw_usdt: Decimal = Decimal("0")
    withdraw_fee_usdt: Decimal = Decimal("0")
    destination_address: str
    network: str


class FundTransferPreviewOut(WithdrawableCustomerOut):
    pass


class FundTransferExecuteOut(BaseModel):
    ok: bool = True
    transfer_id: str
    amount_usdt: Decimal
    withdraw_fee_usdt: Decimal
    futures_transferred_usdt: Decimal
    binance_withdraw_id: str | None = None
    destination_address: str
    network: str
    message: str


class FundTransferHistoryOut(BaseModel):
    id: str
    customer_id: str
    customer_email: str | None = None
    platform_admin_email: str | None = None
    amount_usdt: Decimal
    withdraw_fee_usdt: Decimal | None = None
    futures_transferred_usdt: Decimal | None = None
    destination_address: str
    network: str
    binance_withdraw_id: str | None = None
    status: str
    error_message: str | None = None
    created_at: datetime | None = None
