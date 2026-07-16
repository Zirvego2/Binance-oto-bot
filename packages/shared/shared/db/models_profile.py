"""Musteri profil baglantilari (Binance, Telegram, OpenAI vb.)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class AdminProfile(Base, TimestampMixin):
    __tablename__ = "admin_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str] = mapped_column(String(36), ForeignKey("admins.id"), unique=True, nullable=False, index=True)

    binance_api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    binance_api_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    telegram_bot_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    openai_api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
