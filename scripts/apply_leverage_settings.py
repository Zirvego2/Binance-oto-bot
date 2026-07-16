"""Kaldirac ust sinirini 20x, varsayilan kaldiraci 10x yapar."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "trading_bot.db"


def main() -> None:
    if not DB.exists():
        print(f"Veritabani bulunamadi: {DB}")
        return

    conn = sqlite3.connect(DB)
    conn.execute(
        """
        UPDATE bot_settings
        SET max_allowed_leverage = 20,
            leverage = 10
        WHERE id = 'default'
        """
    )
    conn.commit()
    row = conn.execute(
        "SELECT leverage, max_allowed_leverage FROM bot_settings WHERE id = 'default'"
    ).fetchone()
    print("Guncel kaldirac ayarlari:", row)
    conn.close()


if __name__ == "__main__":
    main()
