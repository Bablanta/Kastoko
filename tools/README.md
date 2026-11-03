# 🛠️ Panduan Utilitas & Tools KasToko

Folder ini berisi skrip pemeliharaan, sinkronisasi, dan manajemen sistem KasToko.

---

### 1. 🚀 `deploy_manager.py` & `deploy_ke_ubuntu.bat`
Tool untuk mengunggah update kode program dan/atau menyinkronkan database antara PC Lokal (Windows) dan Server Ubuntu (`192.168.1.8`).
- **Cara Menjalankan**:
  - Di Windows: Cukup klik ganda `deploy_ke_ubuntu.bat` (tersedia di folder utama dan di folder `tools/`).
  - Di CLI / Terminal:
    ```bash
    python tools/deploy_manager.py code     # Update file kode saja (Database transaksi server AMAN)
    python tools/deploy_manager.py pull_db  # Ambil database dari Ubuntu ke lokal
    python tools/deploy_manager.py full     # Sinkronkan kode + timpa database lokal ke server
    ```

---

### 2. 🐧 `deploy.sh`
Skrip otomatisasi di server Ubuntu.
- **Cara Menjalankan** di terminal Ubuntu:
  ```bash
  cd /home/bablanta/Kastoko
  bash tools/deploy.sh
  ```
  *Fungsi: Mengambil commit terbaru dari GitHub, mereset kode ke `origin/main`, dan merestart PM2.*

---

### 3. 💾 `db_backup.py`
Utilitas untuk membuat salinan cadangan (*backup*) instan dari `pembukuan.db` ke folder `backup/`.
- Menyimpan file dengan format timestamp: `pembukuan_manual_YYYYMMDD_HHMMSS.db`.
- Memeriksa integritas SQLite (`PRAGMA integrity_check`) dan menampilkan jumlah baris data.
- **Cara Menjalankan**:
  ```bash
  python tools/db_backup.py
  ```

---

### 4. 🔍 `db_inspect.py`
Utilitas CLI untuk mengecek kesehatan dan ringkasan data database tanpa membuka aplikasi.
- Menampilkan status integritas SQLite.
- Menampilkan daftar akun aktif dan tarif persentase bagi hasil teknisi.
- Menampilkan rincian jumlah tiket servis berdasarkan status pengerjaan.
- Menampilkan ringkasan omset, modal SPP, biaya operasional (OPP), dan laba bersih.
- **Cara Menjalankan**:
  ```bash
  python tools/db_inspect.py
  ```
