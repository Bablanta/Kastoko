# -*- coding: utf-8 -*-
"""
tools/sync_from_server.py - Download / Deploy Utuh Seluruh File & Database dari Server Ubuntu ke Lokal
"""
import os
import sys
import shutil
import hashlib
import datetime
import paramiko
import sqlite3
import subprocess

UBUNTU_HOST = "192.168.1.8"
UBUNTU_USER = "bablanta"
REMOTE_DIR = "/home/bablanta/Kastoko"

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DIR = os.path.abspath(os.path.join(TOOLS_DIR, ".."))

EXCLUDE_DIRS = {".git", "__pycache__", ".gemini", "backup", "scratch", ".venv"}
EXCLUDE_FILES = {".pyc", ".tmp", ".log"}

def md5_file(filepath):
    if not os.path.exists(filepath):
        return None
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def create_local_backup():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(LOCAL_DIR, "backup", f"snapshot_pre_pull_utuh_{ts}")
    os.makedirs(backup_path, exist_ok=True)
    print(f"\n[1/5] Membuat snapshot cadangan lokal sebelum sinkronisasi...")
    print(f"      Lokasi cadangan: backup/{os.path.basename(backup_path)}")

    # Backup file-file penting
    for item in os.listdir(LOCAL_DIR):
        if item in EXCLUDE_DIRS:
            continue
        src = os.path.join(LOCAL_DIR, item)
        dst = os.path.join(backup_path, item)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
        elif os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
    print("      ✓ Snapshot cadangan lokal berhasil disimpan.")
    return backup_path

def download_remote_tree(sftp, remote_dir, local_dir):
    downloaded = 0
    os.makedirs(local_dir, exist_ok=True)

    for item in sftp.listdir_attr(remote_dir):
        r_path = f"{remote_dir}/{item.filename}"
        l_path = os.path.join(local_dir, item.filename)

        # Cek tipe (directory vs file)
        is_dir = (item.st_mode & 0o040000) != 0

        if is_dir:
            if item.filename in EXCLUDE_DIRS:
                continue
            downloaded += download_remote_tree(sftp, r_path, l_path)
        else:
            if any(item.filename.endswith(ext) for ext in EXCLUDE_FILES):
                continue
            
            # Download file
            needs_down = True
            if os.path.exists(l_path):
                l_size = os.path.getsize(l_path)
                if l_size == item.st_size and abs(int(os.path.getmtime(l_path)) - item.st_mtime) < 2:
                    needs_down = False

            if needs_down:
                sftp.get(r_path, l_path)
                try:
                    sftp_mtime = item.st_mtime
                    os.utime(l_path, (sftp_mtime, sftp_mtime))
                except Exception:
                    pass
                rel_name = os.path.relpath(l_path, LOCAL_DIR)
                print(f"  ✓ Download: {rel_name} ({item.st_size:,} bytes)")
                downloaded += 1
            else:
                rel_name = os.path.relpath(l_path, LOCAL_DIR)
                print(f"  - Identik: {rel_name} ({item.st_size:,} bytes)")

    return downloaded

def main():
    print("=" * 65)
    print("    KASTOKO - DEPLOY UTUH DARI SERVER UBUNTU KE PC LOKAL")
    print("=" * 65)
    print(f"Sumber (Server) : {UBUNTU_USER}@{UBUNTU_HOST}:{REMOTE_DIR}")
    print(f"Tujuan (Lokal)  : {LOCAL_DIR}")
    print("-" * 65)

    # 1. Backup
    create_local_backup()

    # 2. Hubungkan SSH/SFTP
    print(f"\n[2/5] Menghubungi Server Ubuntu ({UBUNTU_HOST})...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    try:
        if os.path.exists(key_path):
            client.connect(UBUNTU_HOST, username=UBUNTU_USER, key_filename=key_path, timeout=5)
        else:
            client.connect(UBUNTU_HOST, username=UBUNTU_USER, password="1234", timeout=5)
        print("      ✓ Terhubung ke server Ubuntu.")
    except Exception as e:
        print(f"      [ERROR] Gagal konek ke Ubuntu: {e}")
        sys.exit(1)

    sftp = client.open_sftp()

    # 3. Download Semua File Utuh
    print(f"\n[3/5] Mengunduh seluruh file & database dari server ke lokal...")
    count = download_remote_tree(sftp, REMOTE_DIR, LOCAL_DIR)
    print(f"\n      ✓ Total {count} file berhasil disinkronkan dari server!")

    sftp.close()
    client.close()

    # 4. Verifikasi Integritas Database & Kode
    print(f"\n[4/5] Memverifikasi integritas sistem lokal...")
    db_path = os.path.join(LOCAL_DIR, "pembukuan.db")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("PRAGMA integrity_check")
        status = c.fetchone()[0]
        srv_count = c.execute("SELECT count(*) FROM services").fetchone()[0]
        trx_count = c.execute("SELECT count(*) FROM transactions").fetchone()[0]
        conn.close()
        print(f"      ✓ Database SQLite: {status.upper()}")
        print(f"        - Total Servis     : {srv_count} tiket")
        print(f"        - Total Transaksi  : {trx_count} transaksi")
    else:
        print(f"      [!] File pembukuan.db tidak ditemukan!")

    idx_path = os.path.join(LOCAL_DIR, "index.html")
    if os.path.exists(idx_path):
        print(f"      ✓ File index.html : {os.path.getsize(idx_path):,} bytes (Tersedia)")

    print("-" * 65)
    print("  [SELESAI] Seluruh file KasToko telah dideploy utuh dari server ke lokal!")
    print("=" * 65)

if __name__ == "__main__":
    main()
