"""SQLite icin BTC impuls migration kolonlarini uygular."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "trading_bot.db"

SETTINGS_COLUMNS = [
    ("impulse_mode", "VARCHAR(16) NOT NULL DEFAULT 'OFF'"),
    ("impulse_btc_min_change_pct", "NUMERIC(10,4) NOT NULL DEFAULT 0.35"),
    ("impulse_lookback_minutes", "INTEGER NOT NULL DEFAULT 3"),
    ("impulse_extreme_min_score", "NUMERIC(10,4) NOT NULL DEFAULT 50"),
    ("impulse_max_entries", "INTEGER NOT NULL DEFAULT 3"),
    ("impulse_margin_usdt", "NUMERIC(18,8) NOT NULL DEFAULT 5"),
    ("impulse_leverage", "INTEGER NOT NULL DEFAULT 8"),
    ("impulse_tp_roi_pct", "NUMERIC(10,4) NOT NULL DEFAULT 4"),
    ("impulse_sl_roi_pct", "NUMERIC(10,4) NOT NULL DEFAULT 20"),
    ("impulse_cooldown_minutes", "INTEGER NOT NULL DEFAULT 20"),
    ("impulse_top_n_scan", "INTEGER NOT NULL DEFAULT 25"),
    ("impulse_rsi_overbought", "NUMERIC(10,4) NOT NULL DEFAULT 70"),
    ("impulse_rsi_oversold", "NUMERIC(10,4) NOT NULL DEFAULT 30"),
    ("impulse_check_interval_seconds", "INTEGER NOT NULL DEFAULT 20"),
]

RUNTIME_COLUMNS = [
    ("impulse_last_event_at", "DATETIME"),
    ("impulse_last_direction", "VARCHAR(8)"),
    ("impulse_last_btc_change_pct", "NUMERIC(10,4)"),
    ("impulse_last_opened_count", "INTEGER NOT NULL DEFAULT 0"),
    ("impulse_last_scan_at", "DATETIME"),
]


def _add_columns(cur: sqlite3.Cursor, table: str, columns: list[tuple[str, str]]) -> None:
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    for name, col_type in columns:
        if name not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")
            print(f"  + {table}.{name}")


def main() -> None:
    if not DB_PATH.exists():
        print(f"DB bulunamadi: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print("bot_settings kolonlari...")
    _add_columns(cur, "bot_settings", SETTINGS_COLUMNS)
    print("bot_runtime_status kolonlari...")
    _add_columns(cur, "bot_runtime_status", RUNTIME_COLUMNS)

    cur.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
    cur.execute("DELETE FROM alembic_version")
    cur.execute("INSERT INTO alembic_version (version_num) VALUES ('c3d4e5f6a7b8')")

    conn.commit()
    conn.close()
    print("Impuls migration tamamlandi.")


if __name__ == "__main__":
    main()
