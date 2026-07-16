import sqlite3
from pathlib import Path

root = Path(r"C:/Users/Ali/Desktop/Binance-Oto-Bot")
for db in sorted(root.glob("*.db")):
    c = sqlite3.connect(db)
    tables = [
        r[0]
        for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic_%'"
        ).fetchall()
    ]
    print(f"\n=== {db.name} ===")
    total = 0
    for t in sorted(tables):
        n = c.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        if n:
            print(f"  {t}: {n}")
            total += n
    print(f"  TOPLAM kayit: {total}")
    admins = []
    if "admins" in tables:
        cols = [r[1] for r in c.execute("PRAGMA table_info(admins)").fetchall()]
        if "firebase_uid" in cols:
            admins = c.execute("SELECT email, firebase_uid FROM admins").fetchall()
        else:
            admins = c.execute("SELECT email FROM admins").fetchall()
    if admins:
        print("  admins:", admins)
    c.close()
