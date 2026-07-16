"""Muzaffer son islemler diagnostic."""

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
    from sqlalchemy import desc, select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from shared.db import Admin, Position, Trade

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        admin = (await session.execute(select(Admin).where(Admin.email == "muzaffer@gmail.com"))).scalar_one_or_none()
        if not admin:
            print("Admin not found")
            return

        print(f"admin_id={admin.id}\n")

        trades = (
            await session.execute(
                select(Trade)
                .where(Trade.admin_id == admin.id)
                .order_by(desc(Trade.closed_at))
                .limit(5)
            )
        ).scalars().all()

        print("=== SON 5 KAPANMIS ISLEM ===")
        for t in trades:
            print("---")
            print(f"symbol={t.symbol} side={t.side} closed_at={t.closed_at}")
            print(f"  close_reason={t.close_reason} open_reason={t.open_reason}")
            print(f"  entry={t.entry_price} exit={t.exit_price}")
            print(f"  margin={t.margin_usdt} leverage={t.leverage}x qty={t.quantity}")
            print(f"  SL={t.stop_loss_price} TP={t.take_profit_price}")
            print(f"  gross_pnl={t.gross_pnl_usdt} net_pnl={t.net_pnl_usdt} net_roi={t.net_roi_pct}%")
            print(f"  commission open/close={t.open_commission_usdt}/{t.close_commission_usdt} funding={t.funding_fee_usdt}")
            print(f"  position_id={t.position_id}")

        pos_ids = [t.position_id for t in trades[:2]]
        if pos_ids:
            positions = (
                await session.execute(select(Position).where(Position.id.in_(pos_ids)))
            ).scalars().all()
            print("\n=== ILGILI POZISYON KAYITLARI ===")
            for p in positions:
                print("---")
                print(f"symbol={p.symbol} status={p.status} side={p.side}")
                print(f"  opened={p.opened_at} closed={p.closed_at}")
                print(f"  entry={p.entry_price} exit={p.exit_price} mark={p.mark_price}")
                print(f"  margin={p.margin_usdt} loss_add_count={p.loss_add_count}")
                print(f"  SL={p.stop_loss_price} TP={p.take_profit_price}")
                print(f"  close_reason={p.close_reason} unrealized={p.unrealized_pnl} roi={p.roi_pct}")


if __name__ == "__main__":
    asyncio.run(main())
