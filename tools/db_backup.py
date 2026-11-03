# -*- coding: utf-8 -*-
"""
tools/db_backup.py - Utilitas Backup Manual Database KasToko (pembukuan.db)
"""

import os
import sys
import shutil
import datetime
import sqlite3

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(TOOLS_DIR, ".."))
DB_PATH = os.path.join(ROOT_DIR, "pembukuan.db")
BACKUP_DIR = os.path.join(ROOT_DIR, "backup")

def main():
    print("=" * 60)
    print("      KASTOKO - TOOL BACKUP DATABASE (pembukuan.db)")
    print("=" * 60)

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database {DB_PATH} tidak ditemukan!")
        sys.exit(1)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"pembukuan_manual_{ts}.db"
    dest_path = os.path.join(BACKUP_DIR, backup_filename)

    # Lakukan copy database
    shutil.copy2(DB_PATH, dest_path)
    file_size = os.path.getsize(dest_path)
    print(f"✓ Backup berhasil dibuat: backup/{backup_filename} ({file_size:,} bytes)")

    # Pengecekan integritas SQLite
    try:
        conn = sqlite3.connect(dest_path)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()[0]
        if res == "ok":
            print("✓ Integritas SQLite: OK (Database sehat & valid)")
        else:
            print(f"[!] Peringatan integritas: {res}")

        # Tampilkan ringkasan isi tabel
        print("\nRingkasan Data Tersimpan:")
        tables = ["transactions", "services", "users", "settings"]
        for tbl in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl};")
                count = cur.fetchone()[0]
                print(f"  - Tabel {tbl:<14}: {count:,} baris")
            except Exception:
                pass
        conn.close()
    except Exception as e:
        print(f"[!] Gagal mengecek integritas database: {e}")

    print("=" * 60)

if __name__ == "__main__":
    main()
