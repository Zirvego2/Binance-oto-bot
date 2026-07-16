"""Admin LIVE gelismis motor onayi — backend minimumlari zorunlu."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP = ROOT / "scripts" / "stop_bot.ps1"
START = ROOT / "scripts" / "start_bot.ps1"

MIN_SHADOW = 100
MIN_PAPER_TRADES = 30
REQUIRED_PHRASE = "GELİŞMİŞ KARAR MOTORUNU CANLIDA AÇ"


def _resolve_db_path() -> Path:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"')
                if "sqlite" in url and ":///" in url:
                    return Path(url.split("///", 1)[1])
    return ROOT / "trading_bot.db"


DB = _resolve_db_path()


def _counts(conn: sqlite3.Connection) -> dict:
    c = conn.cursor()
    return {
        "open_positions": c.execute("SELECT COUNT(1) FROM positions WHERE status='OPEN'").fetchone()[0],
        "shadow_decisions": c.execute("SELECT COUNT(1) FROM shadow_decisions").fetchone()[0],
        "paper_trades": c.execute("SELECT COUNT(1) FROM trades WHERE bot_mode='paper'").fetchone()[0],
        "bot_enabled": c.execute("SELECT bot_enabled FROM bot_settings WHERE id='default'").fetchone()[0],
        "run_state": c.execute("SELECT run_state FROM bot_runtime_status WHERE id='default'").fetchone()[0],
        "safe_mode": c.execute("SELECT safe_mode_reason FROM bot_runtime_status WHERE id='default'").fetchone()[0],
    }


def _log_approval(conn: sqlite3.Connection, *, status: str, detail: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO bot_events (id, event_type, message, bot_mode, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), "ENHANCED_LIVE_APPROVAL", f"{status}: {detail}", "live", now, now),
    )


def approve(*, confirmation_text: str | None = None, force_record_only: bool = True) -> None:
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    stats = _counts(conn)
    blockers: list[str] = []

    if stats["shadow_decisions"] < MIN_SHADOW:
        blockers.append(f"shadow karar: {stats['shadow_decisions']}/{MIN_SHADOW}")
    if stats["paper_trades"] < MIN_PAPER_TRADES:
        blockers.append(f"PAPER islem: {stats['paper_trades']}/{MIN_PAPER_TRADES}")
    if stats["open_positions"] > 0:
        blockers.append(f"acik pozisyon: {stats['open_positions']} (0 olmali)")
    if stats["bot_enabled"] or stats["run_state"] == "RUNNING":
        blockers.append("bot calisiyor (once durdurulmali)")
    if stats["safe_mode"]:
        blockers.append(f"SAFE_MODE: {stats['safe_mode']}")

    phrase_ok = confirmation_text == REQUIRED_PHRASE
    if not phrase_ok:
        blockers.append(f"onay metni eksik (beklenen: {REQUIRED_PHRASE!r})")

    if blockers:
        msg = "; ".join(blockers)
        _log_approval(conn, status="BEKLEMEDE", detail=f"Admin onayi alindi ancak LIVE acilamadi — {msg}")
        conn.commit()
        conn.close()
        print("Onayiniz kaydedildi, ancak LIVE gelismis motor henuz ACILAMAZ:")
        for b in blockers:
            print(f"  - {b}")
        print("\nShadow mod devam ediyor. Kosullar saglandiginda tekrar calistirin:")
        print(f'  python scripts/approve_enhanced_live.py --text "{REQUIRED_PHRASE}"')
        return

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        UPDATE bot_settings
        SET enhanced_engine_live_enabled=1,
            enhanced_engine_enabled=1,
            updated_at=?
        WHERE id='default'
        """,
        (now,),
    )
    _log_approval(conn, status="AKTIF", detail="LIVE gelismis karar motoru admin onayi ile acildi")
    conn.commit()
    conn.close()

    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(STOP)], cwd=ROOT, check=False)
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(START)], cwd=ROOT, check=True)
    print("LIVE gelismis karar motoru AKTIF edildi. Worker yeniden baslatildi.")


if __name__ == "__main__":
    text = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--text":
        text = sys.argv[2]
    elif len(sys.argv) == 2:
        text = sys.argv[1]
    # Kullanici sadece "onay veriyorum" dediyse kayit + blocker listesi
    approve(confirmation_text=text or "onay veriyorum")
