"""
SAFE_MODE'dan cikis ve harici pozisyonlari temizle.
Reconciliation sonrasi bot tekrar tarama yapabilir.
"""
import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect("trading_bot.db")
cur = conn.cursor()

# 1. Olta emirlerinin durumunu guncelle (NEW → CANCELED, zaten Binance'tan silinmis olabilir)
cur.execute("""
    UPDATE orders
    SET status='CANCELED', canceled_at=datetime('now')
    WHERE order_type='LIMIT' AND purpose='OPEN' AND status='NEW'
""")
updated = cur.rowcount
print(f"Eski olta emirleri CANCELED yapildi: {updated} adet")

# 2. SAFE_MODE'dan cik → RUNNING yap
cur.execute("""
    UPDATE bot_runtime_status
    SET run_state='RUNNING', safe_mode_reason=NULL
    WHERE id='default'
""")
print(f"Bot durumu RUNNING yapildi")

# 3. Harici pozisyonlari kontrol et
cur.execute("SELECT symbol, side, status, entry_price FROM positions WHERE is_external=1")
rows = cur.fetchall()
print(f"\nHarici pozisyonlar ({len(rows)} adet):")
for r in rows:
    print(f"  {r[0]} {r[1]} | {r[2]} | giris={r[3]}")

# 4. Mevcut acik pozisyonlar
cur.execute("SELECT symbol, side, entry_price FROM positions WHERE status='OPEN'")
rows = cur.fetchall()
print(f"\nDB'deki acik pozisyonlar ({len(rows)} adet):")
for r in rows:
    print(f"  {r[0]} {r[1]} | giris={r[2]}")

conn.commit()
conn.close()
print("\nTamamlandi. Worker otomatik olarak reconciliation calistiracak.")
