"""Sinyal/pozisyon diagnostik scripti."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "trading_bot.db"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("=== BOT SETTINGS ===")
    row = c.execute(
        """SELECT bot_enabled, auto_trading_enabled, mode, long_enabled, short_enabled,
           market_direction_filter_enabled, limit_entry_enabled, min_signal_score,
           max_open_positions, scan_interval_seconds, margin_per_trade_usdt, leverage,
           daily_max_loss_usdt, max_consecutive_losses
           FROM bot_settings WHERE id='default'"""
    ).fetchone()
    if row:
        print(dict(row))

    print("\n=== RUNTIME ===")
    row = c.execute(
        """SELECT run_state, safe_mode_reason, last_scan_at, last_signal_at,
           last_order_at, worker_heartbeat_at FROM bot_runtime_status WHERE id='default'"""
    ).fetchone()
    if row:
        print(dict(row))

    print("\n=== OPEN POSITIONS ===", c.execute("SELECT COUNT(1) FROM positions WHERE status='OPEN'").fetchone()[0])

    print("\n=== RISK SKIP REASONS (2h) ===")
    for r in c.execute(
        """SELECT reason, COUNT(1) cnt FROM analysis_results
           WHERE decision='RISK_NEDENIYLE_ATLANDI' AND created_at >= datetime('now', '-2 hours')
           GROUP BY reason ORDER BY cnt DESC LIMIT 12"""
    ):
        print(dict(r))

    print("\n=== RECENT SIGNALS ===")
    for r in c.execute(
        "SELECT created_at, symbol, side, total_score, consumed FROM strategy_signals ORDER BY created_at DESC LIMIT 12"
    ):
        print(dict(r))

    print("\n=== RECENT ANALYSIS ===")
    for r in c.execute(
        "SELECT created_at, symbol, decision, reason FROM analysis_results ORDER BY created_at DESC LIMIT 15"
    ):
        d = dict(r)
        d["reason"] = (d.get("reason") or "")[:90]
        print(d)

    print("\n=== ANALYSIS DECISION COUNTS (6h) ===")
    for r in c.execute(
        """SELECT decision, COUNT(1) cnt FROM analysis_results
           WHERE created_at >= datetime('now', '-6 hours') GROUP BY decision ORDER BY cnt DESC"""
    ):
        print(dict(r))

    print("\n=== RECENT RISK EVENTS ===")
    for r in c.execute(
        "SELECT created_at, severity, event_type, message FROM risk_events ORDER BY created_at DESC LIMIT 15"
    ):
        d = dict(r)
        d["message"] = (d.get("message") or "")[:100]
        print(d)

    print("\n=== RECENT BOT EVENTS ===")
    for r in c.execute(
        "SELECT created_at, event_type, message FROM bot_events ORDER BY created_at DESC LIMIT 20"
    ):
        d = dict(r)
        d["message"] = (d.get("message") or "")[:120]
        print(d)

    print("\n=== DAILY STATS ===")
    for r in c.execute(
        "SELECT stat_date, trades_count, net_pnl_usdt, consecutive_losses FROM daily_statistics ORDER BY stat_date DESC LIMIT 3"
    ):
        print(dict(r))

    conn.close()


if __name__ == "__main__":
    main()
