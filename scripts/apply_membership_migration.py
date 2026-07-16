"""Musteri uyelik alanlarini SQLite'a ekler ve mevcut onayli musterilere 5 yil tanir."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "trading_bot.db"
LEGACY_DAYS = 5 * 365
REVISION = "n3o4p5q6r7s8"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"DB bulunamadi: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cols = {row[1] for row in cur.execute("PRAGMA table_info(admins)").fetchall()}
    for col, ddl in [
        ("membership_plan", "ALTER TABLE admins ADD COLUMN membership_plan VARCHAR(32)"),
        ("membership_starts_at", "ALTER TABLE admins ADD COLUMN membership_starts_at DATETIME"),
        ("membership_expires_at", "ALTER TABLE admins ADD COLUMN membership_expires_at DATETIME"),
    ]:
        if col not in cols:
            cur.execute(ddl)
            print(f"Added column: {col}")

    rows = cur.execute(
        """
        SELECT id, approved_at, created_at
        FROM admins
        WHERE role = 'customer'
          AND approval_status = 'approved'
          AND membership_expires_at IS NULL
        """
    ).fetchall()

    now = datetime.now(timezone.utc)
    for admin_id, approved_at, created_at in rows:
        anchor_raw = approved_at or created_at
        if anchor_raw:
            anchor = datetime.fromisoformat(str(anchor_raw).replace("Z", "+00:00"))
            if anchor.tzinfo is None:
                anchor = anchor.replace(tzinfo=timezone.utc)
        else:
            anchor = now
        expires = anchor + timedelta(days=LEGACY_DAYS)
        cur.execute(
            """
            UPDATE admins
            SET membership_plan = ?, membership_starts_at = ?, membership_expires_at = ?
            WHERE id = ?
            """,
            ("legacy_5y", anchor.isoformat(), expires.isoformat(), admin_id),
        )

    cur.execute(
        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
    )
    cur.execute("DELETE FROM alembic_version")
    cur.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (REVISION,))
    conn.commit()
    conn.close()
    print(f"Backfilled {len(rows)} approved customers with {LEGACY_DAYS} days")
    print(f"Alembic stamped: {REVISION}")


if __name__ == "__main__":
    main()
