"""Botu tam aktif hale getirir: ayarlar + runtime + servisler."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "trading_bot.db"
SCRIPTS = ROOT / "scripts"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
STOP = ROOT / "scripts" / "stop_bot.ps1"
START = ROOT / "scripts" / "start_bot.ps1"

sys.path.insert(0, str(SCRIPTS))
from apply_scalp_settings import SCALP_SETTINGS  # noqa: E402


def activate_db() -> None:
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    now = datetime.now(timezone.utc).isoformat()

    set_clause = ", ".join(f"{k}=?" for k in SCALP_SETTINGS)
    conn.execute(
        f"UPDATE bot_settings SET {set_clause}, live_trading_enabled=1 WHERE id='default'",
        tuple(SCALP_SETTINGS.values()),
    )

    exists = conn.execute("SELECT id FROM bot_runtime_status WHERE id='default'").fetchone()
    if exists:
        conn.execute(
            """
            UPDATE bot_runtime_status SET
                run_state = 'RUNNING',
                started_at = ?,
                stopped_at = NULL,
                safe_mode_reason = NULL
            WHERE id = 'default'
            """,
            (now,),
        )
    else:
        conn.execute(
            """
            INSERT INTO bot_runtime_status (id, run_state, started_at)
            VALUES ('default', 'RUNNING', ?)
            """,
            (now,),
        )

    conn.commit()
    row = conn.execute(
        "SELECT bot_enabled, auto_trading_enabled, mode, leverage, margin_per_trade_usdt, run_state "
        "FROM bot_settings bs JOIN bot_runtime_status br ON br.id='default' WHERE bs.id='default'"
    ).fetchone()
    conn.close()
    print("DB aktif:", row)


def restart_services() -> None:
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(STOP)],
        cwd=ROOT,
        check=False,
    )
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(START)],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    if not DB.exists():
        sys.exit(f"DB yok: {DB}")
    activate_db()
    restart_services()
    print("\nBot AKTIF — LIVE, 20 USDT x7, otomatik islem acik.")
