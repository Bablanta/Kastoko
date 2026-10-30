# -*- coding: utf-8 -*-
"""
sync_direct_lan.py - Deploy Langsung dari PC Lokal ke Server Ubuntu via LAN (100% Offline, Tanpa GitHub)
"""

import os
import sys
import paramiko

# Pastikan output konsol aman dari error encoding Windows cp1252
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UBUNTU_HOST = "192.168.1.8"
UBUNTU_USER = "bablanta"
REMOTE_DIR = "/home/bablanta/Kastoko"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

# File / folder yang TIDAK boleh ditimpa agar database server tidak terganggu
EXCLUDE_LIST = {
    "pembukuan.db",
    "backup",
    ".git",
    "__pycache__",
    ".gemini",
    "transactions.json",
    "deploy_langsung_lan.bat",
    "deploy_ke_ubuntu.bat"
}

def sync_direct():
    print("=" * 65)
    print("   [DEPLOY LANGSUNG] PC LOKAL -> UBUNTU SERVER (OFFLINE LAN)")
    print("=" * 65)
    print(f"Target Server : {UBUNTU_USER}@{UBUNTU_HOST}:{REMOTE_DIR}")
    print(f"Sumber Lokal  : {LOCAL_DIR}")
    print("-" * 65)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Gunakan kunci SSH yang sudah terpasang di Windows
    key_path = os.path.expanduser("~/.ssh/id_ed25519")
    try:
        if os.path.exists(key_path):
            client.connect(UBUNTU_HOST, username=UBUNTU_USER, key_filename=key_path, timeout=5)
        else:
            client.connect(UBUNTU_HOST, username=UBUNTU_USER, password="1234", timeout=5)
    except Exception as e:
        print(f"\n[ERROR] Gagal terhubung ke Ubuntu {UBUNTU_HOST} via SSH: {e}")
        print("Pastikan server Ubuntu menyala dan berada dalam 1 jaringan Wi-Fi/LAN yang sama.")
        return False

    sftp = client.open_sftp()
    print("[OK] Terhubung ke server Ubuntu via SSH & SFTP!")
    print("\n[1/2] Menyinkronkan file kode ke server...")

    uploaded_count = 0
    for root, dirs, files in os.walk(LOCAL_DIR):
        # Filter direktori yang dikecualikan
        dirs[:] = [d for d in dirs if d not in EXCLUDE_LIST]
        
        rel_root = os.path.relpath(root, LOCAL_DIR)
        remote_root = REMOTE_DIR if rel_root == "." else os.path.join(REMOTE_DIR, rel_root).replace("\\", "/")

        for file in files:
            if file in EXCLUDE_LIST or file.endswith(".pyc") or file.endswith(".tmp"):
                continue

            local_file = os.path.join(root, file)
            remote_file = os.path.join(remote_root, file).replace("\\", "/")

            try:
                local_size = os.path.getsize(local_file)
                local_mtime = int(os.path.getmtime(local_file))
                needs_upload = True
                try:
                    r_stat = sftp.stat(remote_file)
                    # Upload jika ukuran berbeda atau mtime lokal lebih baru
                    if r_stat.st_size == local_size and abs(r_stat.st_mtime - local_mtime) < 2:
                        needs_upload = False
                except IOError:
                    needs_upload = True

                if needs_upload:
                    sftp.put(local_file, remote_file)
                    # Sinkronkan mtime agar tidak upload berulang jika file tidak berubah
                    try:
                        sftp.utime(remote_file, (local_mtime, local_mtime))
                    except Exception:
                        pass
                    rel_name = os.path.relpath(local_file, LOCAL_DIR)
                    print(f"  -> Mengunggah: {rel_name} ({local_size:,} bytes)")
                    uploaded_count += 1
            except Exception as fe:
                print(f"  [!] Gagal mengunggah {file}: {fe}")

    sftp.close()
    if uploaded_count == 0:
        print("  Semua file di server sudah sama persis dengan PC lokal (tidak ada perubahan).")
    else:
        print(f"[OK] Berhasil mengunggah {uploaded_count} file terbaru langsung ke server!")

    print("\n[2/2] Me-restart server KasToko di Ubuntu (PM2)...")
    stdin, stdout, stderr = client.exec_command("npx pm2 restart Kastoko")
    exit_status = stdout.channel.recv_exit_status()
    
    if exit_status == 0:
        print("[OK] Server KasToko di Ubuntu berhasil direstart!")
        print("-" * 65)
        print("  [BERHASIL] Seluruh fitur terbaru di PC lokal telah aktif di Ubuntu!")
        print(f"  Buka browser di: http://{UBUNTU_HOST}:8080")
        print("=" * 65)
        client.close()
        return True
    else:
        print(f"[ERROR] Gagal restart PM2: {stderr.read().decode()}")
        client.close()
        return False

if __name__ == "__main__":
    success = sync_direct()
    if not success:
        sys.exit(1)
