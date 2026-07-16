import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "trading_bot.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
print("=== LAST 15 POSITIONS ===")
for p in c.execute(
    "SELECT symbol, side, status, bot_mode, opened_at, closed_at, id FROM positions ORDER BY opened_at DESC LIMIT 15"
):
    print(dict(p))
print("\nOPEN total:", c.execute("SELECT COUNT(*) FROM positions WHERE status='OPEN'").fetchone()[0])
print("OPEN live:", c.execute("SELECT COUNT(*) FROM positions WHERE status='OPEN' AND bot_mode='live'").fetchone()[0])
print("CLOSING:", c.execute("SELECT COUNT(*) FROM positions WHERE status='CLOSING'").fetchone()[0])
print("\n=== ALL OPEN ===")
for p in c.execute("SELECT symbol, side, opened_at, loss_add_count FROM positions WHERE status='OPEN' ORDER BY opened_at DESC"):
    print(dict(p))

print("\n=== EVAA ===")
for p in c.execute("SELECT * FROM positions WHERE symbol='EVAAUSDT' ORDER BY opened_at DESC LIMIT 3"):
    print(dict(p))

print("\n=== RECENT EVENTS ===")
for e in c.execute("SELECT created_at, event_type, message FROM bot_events ORDER BY created_at DESC LIMIT 8"):
    print(e[0], e[1], (e[2] or "")[:100])
