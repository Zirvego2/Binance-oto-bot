import sqlite3
from pathlib import Path

c = sqlite3.connect(Path(__file__).resolve().parents[1] / "trading_bot.db", timeout=30)
c.row_factory = sqlite3.Row
bs = c.execute("SELECT mode, bot_enabled, enhanced_engine_enabled, enhanced_engine_shadow_mode, enhanced_engine_live_enabled, shadow_mode_active FROM bot_settings WHERE id='default'").fetchone()
br = c.execute("SELECT run_state, safe_mode_reason FROM bot_runtime_status WHERE id='default'").fetchone()
open_pos = c.execute("SELECT COUNT(1) FROM positions WHERE status='OPEN'").fetchone()[0]
shadow = c.execute("SELECT COUNT(1) FROM shadow_decisions").fetchone()[0]
paper_trades = c.execute("SELECT COUNT(1) FROM trades WHERE bot_mode='paper'").fetchone()[0]
live_trades = c.execute("SELECT COUNT(1) FROM trades WHERE bot_mode='live'").fetchone()[0]
print("settings", dict(bs))
print("runtime", dict(br))
print("open_positions", open_pos)
print("shadow_decisions", shadow)
print("paper_trades", paper_trades, "live_trades", live_trades)
c.close()
