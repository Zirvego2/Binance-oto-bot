"""Hizli scalping ayarlarini bot_settings tablosuna uygular."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "trading_bot.db"

# 20 USDT marj x 7x kaldirac, hizli giris/cikis — gevsetilmis filtreler
SCALP_SETTINGS = {
    "margin_per_trade_usdt": 20,
    "leverage": 7,
    "max_allowed_leverage": 7,
    "take_profit_roi_pct": 4,
    "stop_loss_roi_pct": 2.5,
    "scan_interval_seconds": 30,
    "post_trade_cooldown_minutes": 2,
    "limit_entry_enabled": 0,
    "market_direction_filter_enabled": 0,
    "loss_add_enabled": 0,
    "min_signal_score": 50,
    "min_liquidation_distance_pct": 5,
    "volume_multiplier_min": 1.0,
    "max_volatility_atr_pct": 12,
    "rsi_long_min": 45,
    "rsi_long_max": 70,
    "rsi_short_min": 30,
    "rsi_short_max": 55,
    "top_n_symbols_by_volume": 30,
    "max_open_positions": 10,
    "auto_trading_enabled": 1,
    "bot_enabled": 1,
}

SELECT_COLS = ", ".join(SCALP_SETTINGS.keys())


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"Veritabani bulunamadi: {DB}")

    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row

    before = conn.execute(
        f"SELECT {SELECT_COLS} FROM bot_settings WHERE id='default'"
    ).fetchone()
    if before is None:
        raise SystemExit("bot_settings default satiri yok")

    print("Onceki ayarlar:")
    for k in SCALP_SETTINGS:
        print(f"  {k}: {before[k]}")

    set_clause = ", ".join(f"{k}=?" for k in SCALP_SETTINGS)
    conn.execute(
        f"UPDATE bot_settings SET {set_clause} WHERE id='default'",
        tuple(SCALP_SETTINGS.values()),
    )
    conn.commit()

    after = conn.execute(
        f"SELECT {SELECT_COLS} FROM bot_settings WHERE id='default'"
    ).fetchone()
    print("\nYeni ayarlar (20 USDT x 7x hizli scalping):")
    for k in SCALP_SETTINGS:
        print(f"  {k}: {after[k]}")

    conn.close()
    print("\nTamam. Worker yeniden baslatilirsa ayarlar hemen okunur.")


if __name__ == "__main__":
    main()
