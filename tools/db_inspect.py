# -*- coding: utf-8 -*-
"""
tools/db_inspect.py - Utilitas Inspeksi Cepat Database KasToko (pembukuan.db)
"""

import os
import sys
import sqlite3

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(TOOLS_DIR, ".."))
DB_PATH = os.path.join(ROOT_DIR, "pembukuan.db")

def main():
    print("=" * 65)
    print("      KASTOKO - TOOL INSPEKSI DATABASE (pembukuan.db)")
    print("=" * 65)

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database {DB_PATH} tidak ditemukan!")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Integritas
    cur.execute("PRAGMA integrity_check;")
    chk = cur.fetchone()[0]
    print(f"Status Integritas : {'SEHAT (OK)' if chk == 'ok' else chk}")
    print(f"Ukuran File       : {os.path.getsize(DB_PATH):,} bytes")
    print("-" * 65)

    # 2. Pengguna & Tarif Teknisi
    print("DAFTAR PENGGUNA TOKO:")
    cur.execute("SELECT id, username, fullname, role, status, COALESCE(persen_jasa, 20.0) as persen_jasa FROM users ORDER BY id ASC")
    users = cur.fetchall()
    for u in users:
        pct_info = f"[{u['persen_jasa']}% Jasa]" if u['role'] == 'teknisi' else ""
        print(f"  [{u['id']}] @{u['username']:<12} {u['fullname']:<22} | {u['role'].upper():<10} | {u['status'].upper():<8} {pct_info}")

    # 3. Tiket Servis
    print("\nSTATUS TIKET SERVIS:")
    cur.execute("SELECT status_servis, COUNT(*) as cnt FROM services GROUP BY status_servis")
    statuses = cur.fetchall()
    if not statuses:
        print("  Belum ada tiket servis.")
    else:
        for s in statuses:
            print(f"  - Status {s['status_servis']:<15}: {s['cnt']} unit")

    # 4. Ringkasan Keuangan
    print("\nRINGKASAN PEMBUKUAN (Tabel Transactions):")
    cur.execute("SELECT COUNT(*) as total_trx, COALESCE(SUM(omset), 0) as tot_omset, COALESCE(SUM(spp), 0) as tot_spp, COALESCE(SUM(opp), 0) as tot_opp FROM transactions")
    fin = cur.fetchone()
    tot_omset = fin['tot_omset']
    tot_spp = fin['tot_spp']
    tot_opp = fin['tot_opp']
    laba_bersih = tot_omset - tot_spp - tot_opp

    print(f"  Total Hari Pembukuan : {fin['total_trx']} hari")
    print(f"  Total Omset Servis   : Rp {tot_omset:,.0f}")
    print(f"  Total Modal SPP      : Rp {tot_spp:,.0f}")
    print(f"  Total Biaya OPP      : Rp {tot_opp:,.0f}")
    print(f"  Estimasi Laba Bersih : Rp {laba_bersih:,.0f}")

    conn.close()
    print("=" * 65)

if __name__ == "__main__":
    main()
