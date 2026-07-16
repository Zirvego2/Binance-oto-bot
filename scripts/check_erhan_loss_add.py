"""Erhan hesabi icin zarar ekleme ayarlari ve acik pozisyonlari kontrol eder."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main() -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from shared.db import Admin, BotSettings, Position
    from shared.loss_add import is_normal_market_position, should_loss_add

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    email = "erhan-004@hotmail.com"
    async with Session() as session:
        admin = (await session.execute(select(Admin).where(Admin.email == email))).scalar_one_or_none()
        if admin is None:
            print("Admin bulunamadi")
            return
        settings = (
            await session.execute(select(BotSettings).where(BotSettings.admin_id == admin.id))
        ).scalar_one_or_none()
        if settings is None:
            print("BotSettings bulunamadi")
            return

        print("=== BOT AYARLARI ===")
        print(f"bot_enabled={settings.bot_enabled} mode={settings.mode}")
        print(f"loss_add_enabled={getattr(settings, 'loss_add_enabled', None)}")
        print(f"loss_add_max_count={getattr(settings, 'loss_add_max_count', None)}")
        print(f"loss_add_trigger_roi_pct={getattr(settings, 'loss_add_trigger_roi_pct', None)}")
        print(f"stop_loss_roi_pct={settings.stop_loss_roi_pct}")
        print(f"margin_per_trade={settings.margin_per_trade_usdt} leverage={settings.leverage}")

        positions = (
            await session.execute(
                select(Position)
                .where(Position.admin_id == admin.id, Position.status == "OPEN")
                .order_by(Position.opened_at.desc())
            )
        ).scalars().all()
        print(f"\n=== ACik POZISYONLAR ({len(positions)}) ===")
        for pos in positions:
            normal = is_normal_market_position(is_external=pos.is_external, open_reason=pos.open_reason)
            would_add = should_loss_add(
                pos.roi_pct,
                loss_add_trigger_roi_pct=getattr(settings, "loss_add_trigger_roi_pct", settings.stop_loss_roi_pct),
                stop_loss_roi_pct=settings.stop_loss_roi_pct,
                loss_add_enabled=getattr(settings, "loss_add_enabled", False),
                loss_add_max_count=int(getattr(settings, "loss_add_max_count", 0)),
                loss_add_count=int(getattr(pos, "loss_add_count", 0) or 0),
                is_normal_position=normal,
            )
            print(
                f"{pos.symbol} | side={pos.side} roi={pos.roi_pct}% | "
                f"loss_add_count={getattr(pos, 'loss_add_count', 0)} | "
                f"open_reason={pos.open_reason} external={pos.is_external} | "
                f"would_add={would_add}"
            )


if __name__ == "__main__":
    asyncio.run(main())
