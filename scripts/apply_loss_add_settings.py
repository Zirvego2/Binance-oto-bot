"""Zarar ekleme (-25%) ve nihai stop (-50%) ayarlarini uygular."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "trading_bot.db"


def main() -> None:
    conn = sqlite3.connect(DB)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_settings)").fetchall()]
    if "loss_add_trigger_roi_pct" not in cols:
        conn.execute(
            "ALTER TABLE bot_settings ADD COLUMN loss_add_trigger_roi_pct NUMERIC(10,4) DEFAULT 25"
        )
        print("loss_add_trigger_roi_pct kolonu eklendi")
    conn.execute(
        """
        UPDATE bot_settings
        SET stop_loss_roi_pct = 50,
            loss_add_trigger_roi_pct = 25,
            loss_add_enabled = 1,
            loss_add_max_count = 1
        WHERE id = 'default'
        """
    )
    conn.commit()
    row = conn.execute(
        """
        SELECT stop_loss_roi_pct, loss_add_trigger_roi_pct, loss_add_enabled, loss_add_max_count
        FROM bot_settings WHERE id = 'default'
        """
    ).fetchone()
    print("Guncel ayarlar:", row)
    conn.close()


if __name__ == "__main__":
    main()
