"""Platform odeme / fon transfer kayitlari."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, MONEY_PRECISION, TimestampMixin, new_uuid


class FundTransferLog(Base, TimestampMixin):
    __tablename__ = "fund_transfer_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    platform_admin_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    withdraw_fee_usdt: Mapped[Decimal | None] = mapped_column(Numeric(*MONEY_PRECISION), nullable=True)
    futures_transferred_usdt: Mapped[Decimal | None] = mapped_column(Numeric(*MONEY_PRECISION), nullable=True)
    spot_balance_before_usdt: Mapped[Decimal | None] = mapped_column(Numeric(*MONEY_PRECISION), nullable=True)
    destination_address: Mapped[str] = mapped_column(String(128), nullable=False)
    network: Mapped[str] = mapped_column(String(32), nullable=False)
    binance_withdraw_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
