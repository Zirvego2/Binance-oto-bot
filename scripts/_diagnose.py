import sqlite3
from datetime import datetime, timezone
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "trading_bot.db"
c = sqlite3.connect(db, timeout=60)
c.row_factory = sqlite3.Row

print("=== BOT SETTINGS ===")
s = c.execute("SELECT * FROM bot_settings WHERE id='default'").fetchone()
for k in s.keys():
    if k not in ("created_at", "updated_at", "updated_by_admin_id"):
        print(f"  {k}: {s[k]}")

print("\n=== RUNTIME ===")
r = c.execute("SELECT * FROM bot_runtime_status WHERE id='default'").fetchone()
for k in r.keys():
    print(f"  {k}: {r[k]}")

print("\n=== OPEN POSITIONS ===")
for p in c.execute("SELECT symbol, side, status, opened_at FROM positions WHERE status='OPEN' ORDER BY opened_at DESC"):
    print(f"  {p['symbol']} {p['side']} {p['status']} {p['opened_at']}")

print("\n=== RECENT SIGNALS (10) ===")
for sig in c.execute("SELECT symbol, side, total_score, consumed, created_at FROM strategy_signals ORDER BY created_at DESC LIMIT 10"):
    print(f"  {sig['created_at']} {sig['symbol']} {sig['side']} score={sig['total_score']} consumed={sig['consumed']}")

print("\n=== RECENT ANALYSIS (decision=ISLEM_AC/AC, 10) ===")
for a in c.execute(
    "SELECT analyzed_at, symbol, suggested_side, decision, total_score, reason FROM analysis_results "
    "WHERE decision IN ('ISLEM_AC','AC') ORDER BY analyzed_at DESC LIMIT 10"
):
    print(f"  {a['analyzed_at']} {a['symbol']} {a['suggested_side']} {a['decision']} score={a['total_score']} | {a['reason'][:60]}")

print("\n=== RECENT RISK EVENTS (10) ===")
for e in c.execute("SELECT created_at, event_type, symbol, severity, message FROM risk_events ORDER BY created_at DESC LIMIT 10"):
    print(f"  {e['created_at']} [{e['severity']}] {e['event_type']} {e['symbol'] or '-'} | {e['message'][:80]}")

print("\n=== RECENT BOT EVENTS (10) ===")
for e in c.execute("SELECT created_at, event_type, message FROM bot_events ORDER BY created_at DESC LIMIT 10"):
    print(f"  {e['created_at']} {e['event_type']} | {e['message'][:100]}")

print("\n=== PENDING LIMIT ORDERS ===")
for o in c.execute("SELECT symbol, side, status, created_at FROM orders WHERE purpose='OPEN' AND status IN ('NEW','PENDING','SUBMITTING') ORDER BY created_at DESC LIMIT 5"):
    print(f"  {o['created_at']} {o['symbol']} {o['side']} {o['status']}")

print("\n=== SYSTEM HEALTH ===")
try:
    for h in c.execute("SELECT * FROM system_health LIMIT 5"):
        print(dict(h))
except Exception as e:
    print(f"  (atlandi: {e})")

print("\n=== DECISION COUNTS (last 2h) ===")
for r in c.execute(
    "SELECT decision, COUNT(*) cnt FROM analysis_results "
    "WHERE analyzed_at >= datetime('now', '-2 hours') GROUP BY decision ORDER BY cnt DESC"
):
    print(f"  {r['decision']}: {r['cnt']}")

print("\n=== LATEST 15 ANALYSIS ===")
for a in c.execute(
    "SELECT analyzed_at, symbol, suggested_side, decision, total_score, reason "
    "FROM analysis_results ORDER BY analyzed_at DESC LIMIT 15"
):
    print(f"  {a['analyzed_at']} {a['symbol']} {a['suggested_side']} {a['decision']} score={a['total_score']} | {a['reason'][:55]}")

c.close()
