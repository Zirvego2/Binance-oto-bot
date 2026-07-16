"""Fon transfer log tablosunu SQLite'a ekler."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "trading_bot.db"
REVISION = "o4p5q6r7s8t9"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"DB bulunamadi: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    exists = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fund_transfer_logs'"
    ).fetchone()
    if not exists:
        cur.execute(
            """
            CREATE TABLE fund_transfer_logs (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                customer_id VARCHAR(36) NOT NULL,
                platform_admin_id VARCHAR(36) NOT NULL,
                amount_usdt NUMERIC(18, 8) NOT NULL,
                withdraw_fee_usdt NUMERIC(18, 8),
                futures_transferred_usdt NUMERIC(18, 8),
                spot_balance_before_usdt NUMERIC(18, 8),
                destination_address VARCHAR(128) NOT NULL,
                network VARCHAR(32) NOT NULL,
                binance_withdraw_id VARCHAR(128),
                status VARCHAR(16) NOT NULL,
                error_message TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("CREATE INDEX ix_fund_transfer_logs_customer_id ON fund_transfer_logs (customer_id)")
        cur.execute("CREATE INDEX ix_fund_transfer_logs_platform_admin_id ON fund_transfer_logs (platform_admin_id)")
        cur.execute("CREATE INDEX ix_fund_transfer_logs_status ON fund_transfer_logs (status)")
        print("Created table: fund_transfer_logs")

    cur.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
    cur.execute("DELETE FROM alembic_version")
    cur.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (REVISION,))
    conn.commit()
    conn.close()
    print(f"Alembic stamped: {REVISION}")


if __name__ == "__main__":
    main()
