# -*- coding: utf-8 -*-
"""
deploy_manager.py - Modul Terpadu Deploy & Sinkronisasi KasToko ke Server Ubuntu
Mendukung:
1. Update Kode & Fitur Saja
2. Update Kode + Sinkronisasi Database Pembukuan (pembukuan.db)
3. Download Database dari Server Ubuntu ke PC Lokal
"""

import os
import sys
import datetime
import paramiko

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UBUNTU_HOST = "192.168.1.8"
UBUNTU_USER = "bablanta"
REMOTE_DIR = "/home/bablanta/Kastoko"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

EXCLUDE_DIRS = {".git", "__pycache__", ".gemini", "backup"}
CODE_EXT_EXCLUDE = {".pyc", ".tmp", ".log"}
ALWAYS_EXCLUDE_FILES = {"transactions.json"}

def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    try:
        if os.path.exists(key_path):
            client.connect(UBUNTU_HOST, username=UBUNTU_USER, key_filename=key_path, timeout=5)
        else:
            client.connect(UBUNTU_HOST, username=UBUNTU_USER, password="1234", timeout=5)
        return client
    except Exception as e:
        print(f"\n[ERROR] Gagal terhubung ke Ubuntu {UBUNTU_HOST}: {e}")
        print("Pastikan server Ubuntu menyala dan terhubung dalam 1 jaringan Wi-Fi/LAN.")
        return None

def sync_code_files(sftp):
    uploaded = 0
    for root, dirs, files in os.walk(LOCAL_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        rel_root = os.path.relpath(root, LOCAL_DIR)
        remote_root = REMOTE_DIR if rel_root == "." else os.path.join(REMOTE_DIR, rel_root).replace("\\", "/")

        for file in files:
            if file == "pembukuan.db" or file in ALWAYS_EXCLUDE_FILES or any(file.endswith(ext) for ext in CODE_EXT_EXCLUDE):
                continue

            local_file = os.path.join(root, file)
            remote_file = os.path.join(remote_root, file).replace("\\", "/")

            try:
                local_size = os.path.getsize(local_file)
                local_mtime = int(os.path.getmtime(local_file))
                needs_upload = True
                try:
                    r_stat = sftp.stat(remote_file)
                    if r_stat.st_size == local_size and abs(r_stat.st_mtime - local_mtime) < 2:
                        needs_upload = False
                except IOError:
                    needs_upload = True

                if needs_upload:
                    sftp.put(local_file, remote_file)
                    try:
                        sftp.utime(remote_file, (local_mtime, local_mtime))
                    except Exception:
                        pass
                    rel_name = os.path.relpath(local_file, LOCAL_DIR)
                    print(f"  -> Upload kode: {rel_name} ({local_size:,} bytes)")
                    uploaded += 1
            except Exception as e:
                print(f"  [!] Gagal upload {file}: {e}")
    return uploaded

def sync_database_to_server(client, sftp):
    local_db = os.path.join(LOCAL_DIR, "pembukuan.db")
    remote_db = f"{REMOTE_DIR}/pembukuan.db"
    if not os.path.exists(local_db):
        print("  [!] File pembukuan.db lokal tidak ditemukan!")
        return False

    # Buat backup pembukuan.db di server sebelum ditimpa
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_remote = f"{REMOTE_DIR}/backup/pembukuan_backup_{ts}.db"
    client.exec_command(f"cp {remote_db} {backup_remote} 2>/dev/null || true")

    db_size = os.path.getsize(local_db)
    print(f"  -> Mengunggah database pembukuan.db ({db_size:,} bytes)...")
    sftp.put(local_db, remote_db)
    print(f"  [OK] Database pembukuan.db berhasil disinkronkan ke server (backup tersimpan di server: backup_{ts}.db)")
    return True

def pull_database_from_server(client, sftp):
    local_db = os.path.join(LOCAL_DIR, "pembukuan.db")
    remote_db = f"{REMOTE_DIR}/pembukuan.db"
    
    # Buat backup pembukuan.db lokal dulu
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_local = os.path.join(LOCAL_DIR, "backup", f"pembukuan_local_pre_pull_{ts}.db")
    if os.path.exists(local_db):
        import shutil
        os.makedirs(os.path.join(LOCAL_DIR, "backup"), exist_ok=True)
        shutil.copy2(local_db, backup_local)
        print(f"  [INFO] Backup database lokal dibuat di: backup/{os.path.basename(backup_local)}")

    print("  -> Mengunduh pembukuan.db dari server Ubuntu ke PC lokal...")
    sftp.get(remote_db, local_db)
    print("  [OK] Database lokal berhasil diperbarui dari server Ubuntu!")
    return True

def restart_pm2(client):
    stdin, stdout, stderr = client.exec_command("npx pm2 restart Kastoko")
    exit_code = stdout.channel.recv_exit_status()
    if exit_code == 0:
        print("[OK] Server KasToko di Ubuntu berhasil direstart!")
        return True
    else:
        print(f"[!] Gagal restart PM2: {stderr.read().decode()}")
        return False

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    print("=" * 65)
    print("      KASTOKO - DEPLOY & SINKRONISASI SERVER UBUNTU")
    print("=" * 65)
    print(f"Server Target : {UBUNTU_USER}@{UBUNTU_HOST}:{REMOTE_DIR}")
    print(f"Mode Deploy   : {mode.upper()}")
    print("-" * 65)

    client = get_ssh_client()
    if not client:
        sys.exit(1)

    sftp = client.open_sftp()

    if mode == "pull_db":
        pull_database_from_server(client, sftp)
        sftp.close()
        client.close()
        return

    # 1. Sync kode
    print("\n[1/3] Menyinkronkan file program & tampilan...")
    up = sync_code_files(sftp)
    if up == 0:
        print("  Semua file program di server sudah mutakhir.")
    else:
        print(f"  ✓ {up} file program berhasil diperbarui.")

    # 2. Sync database jika mode full
    if mode == "full":
        print("\n[2/3] Menyinkronkan Database Pembukuan (pembukuan.db)...")
        sync_database_to_server(client, sftp)
    else:
        print("\n[2/3] Database pembukuan server dipertahankan (tidak ditimpa).")

    sftp.close()

    # 3. Restart PM2
    print("\n[3/3] Me-restart proses server di Ubuntu...")
    restart_pm2(client)

    client.close()
    print("-" * 65)
    print("  [SUKSES] KasToko di Server Ubuntu telah aktif dengan data terbaru!")
    print(f"  URL: http://{UBUNTU_HOST}:8080")
    print("=" * 65)

if __name__ == "__main__":
    main()
