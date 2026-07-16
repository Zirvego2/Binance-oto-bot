import sqlite3

conn = sqlite3.connect("trading_bot.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(bot_settings)")
cols = {r[1] for r in cur.fetchall()}
if "market_direction_filter_enabled" not in cols:
    cur.execute(
        "ALTER TABLE bot_settings ADD COLUMN market_direction_filter_enabled BOOLEAN NOT NULL DEFAULT 1"
    )
cur.execute("UPDATE bot_settings SET market_direction_filter_enabled=1 WHERE id='default'")
conn.commit()
conn.close()
print("migration ok")
