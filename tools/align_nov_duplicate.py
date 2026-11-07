# -*- coding: utf-8 -*-
"""
tools/align_nov_duplicate.py
Penyelarasan baris manual duplikasi pada tanggal 06 November 2026 (ID #253)
di server Ubuntu agar murni menjadi pencatatan biaya operasional toko (Opp Toko Rp 190.000).
"""

import os
import sys
import paramiko

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UBUNTU_HOST = "192.168.1.8"
UBUNTU_USER = "bablanta"
REMOTE_DIR = "/home/bablanta/Kastoko"

def run_alignment():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    try:
        if os.path.exists(key_path):
            client.connect(UBUNTU_HOST, username=UBUNTU_USER, key_filename=key_path, timeout=5)
        else:
            client.connect(UBUNTU_HOST, username=UBUNTU_USER, password="1234", timeout=5)
    except Exception as e:
        print(f"[ERROR] Gagal terhubung ke Ubuntu {UBUNTU_HOST}: {e}")
        return False

    print(f"[*] Terhubung ke server Ubuntu {UBUNTU_HOST}")

    # 1. Backup database sebelum perubahan
    backup_cmd = f"mkdir -p {REMOTE_DIR}/backup && cp {REMOTE_DIR}/pembukuan.db {REMOTE_DIR}/backup/pembukuan_before_align_$(date +%Y%m%d_%H%M%S).db"
    stdin, stdout, stderr = client.exec_command(backup_cmd)
    stdout.channel.recv_exit_status()
    print("[+] Backup database di server berhasil dibuat.")

    # 2. Cek transaksi #253 sebelum update
    check_py = f"""python3 -c "
import sqlite3
conn = sqlite3.connect('{REMOTE_DIR}/pembukuan.db')
c = conn.cursor()
c.execute('SELECT id, tanggal, omset, spp, opp, jasa, hasil, catatan, service_id FROM transactions WHERE id = 253')
print(c.fetchone())
conn.close()
" """
    stdin, stdout, stderr = client.exec_command(check_py)
    out = stdout.read().decode('utf-8').strip()
    print(f"[i] Data #253 Saat ini: {out}")

    # 3. Update transaksi #253 agar menjadi murni Opp Toko Rp 190.000
    update_py = f"""python3 -c "
import sqlite3
conn = sqlite3.connect('{REMOTE_DIR}/pembukuan.db')
c = conn.cursor()
c.execute('''
    UPDATE transactions 
    SET omset = 0.0, spp = 0.0, opp = 190000.0, jasa = 0.0, hasil = -190000.0, 
        catatan = 'Operasional Toko Harian (Diselaraskan dari baris manual)', 
        updated_at = datetime('now','localtime') 
    WHERE id = 253 AND service_id IS NULL
''')
conn.commit()
print('Rows affected:', c.rowcount)
conn.close()
" """
    stdin, stdout, stderr = client.exec_command(update_py)
    exit_code = stdout.channel.recv_exit_status()
    update_res = stdout.read().decode('utf-8').strip()

    if exit_code == 0:
        print(f"[+] Update transaksi #253 berhasil dijalankan: {update_res}")
    else:
        err = stderr.read().decode('utf-8')
        print(f"[-] Error update: {err}")
        client.close()
        return False

    # 4. Verifikasi setelah update
    stdin, stdout, stderr = client.exec_command(check_py)
    out_after = stdout.read().decode('utf-8').strip()
    print(f"[+] Data #253 Setelah Diselaraskan: {out_after}")

    # 5. Rekap total tanggal 06 November 2026
    rekap_py = f"""python3 -c "
import sqlite3
conn = sqlite3.connect('{REMOTE_DIR}/pembukuan.db')
c = conn.cursor()
c.execute('''SELECT sum(omset), sum(spp), sum(opp), sum(jasa), sum(hasil) FROM transactions WHERE tanggal = '2026-11-06' ''')
print('Omset|SPP|Opp|Jasa|Hasil:', c.fetchone())
conn.close()
" """
    stdin, stdout, stderr = client.exec_command(rekap_py)
    rekap_out = stdout.read().decode('utf-8').strip()
    print(f"[+] Rekap Bersih Tanggal 06 Nov 2026: {rekap_out}")

    client.close()
    return True

if __name__ == "__main__":
    run_alignment()
