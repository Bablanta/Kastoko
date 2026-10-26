# 📊 Panduan Penggunaan & Dokumentasi CalAseToko

Aplikasi **CalAseToko** adalah aplikasi pembukuan toko modern berbasis web (HTML5, CSS3, JavaScript) dengan backend Python (`server.py`) dan database **SQLite (`pembukuan.db`)** yang mendukung sinkronisasi data real-time antar perangkat dalam jaringan lokal, pembagian hak akses (Superadmin & Admin), visualisasi grafik omset & hasil, riwayat buku toko terpadu (Harian, Mingguan, Bulanan), serta pencadangan database otomatis.

---

## 🚀 1. Menjalankan & Menghentikan Server

### A. Menjalankan Server & Tray Icon
Cukup lakukan *double-click* pada file **`jalankan_server.bat`**.
- Skrip otomatis membuka firewall port `8080`, menampilkan jendela konsol server, dan memunculkan ikon KasToko (**KT**) di **System Tray** (area notifikasi Windows di dekat jam).
- **Minimize to Background (System Tray):**
  - Jendela konsol **TIDAK auto-hide** saat baru dibuka.
  - Namun, ketika Anda menekan tombol **Minimize (`_`)**, jendela server akan **otomatis disembunyikan ke background** dan tersimpan rapi di System Tray agar taskbar tetap bersih.

### B. Menu Klik Kanan di System Tray
Klik kanan pada ikon KasToko di System Tray untuk mengakses menu:
1. **🌐 Open (Buka KasToko):** Membuka dashboard KasToko langsung di peramban web dan memunculkan kembali jendela konsol.
2. **🖥️ Tampilkan/Sembunyikan Jendela Server:** Toggle untuk memunculkan atau menyembunyikan jendela konsol secara manual.
3. **❌ Quit (Keluar):** Menghentikan server Python dan menutup aplikasi secara bersih tanpa meninggalkan proses menggantung.

### C. Cara Menghentikan Server
- Cukup klik kanan ikon Tray KasToko lalu pilih **Quit (Keluar)**.
- Atau jika jendela konsol sedang terbuka, tekan kombinasi tombol `Ctrl + C`.

---

## 🌐 2. Cara Mengakses Aplikasi
Setelah server berjalan, akses browser melalui:
- **Di komputer server:** `http://localhost:8080/index.html`
- **Di komputer lain dalam 1 jaringan Wi-Fi/LAN:** `http://[IP-Komputer-Server]:8080/index.html`

---

## 🔐 3. Hak Akses Pengguna (Role Permissions)

Fitur analitik dan finansial sensitif dirancang khusus hanya dapat diakses penuh oleh **Superadmin**:

| Fitur / Komponen | Superadmin (`super123`) | Admin (`admin123`) |
|---|:---:|:---:|
| Input & Edit Transaksi | ✅ Ya | ✅ Ya |
| Catatan di Transaksi | ✅ Ya | ✅ Ya |
| **Riwayat Buku Toko (Harian / Mingguan / Bulanan)** | ✅ Ya | ✅ Ya |
| Tombol Sembunyikan Riwayat (▲/▼) | ✅ Ya | ✅ Ya |
| Tombol Sembunyikan Form Input | ✅ Ya | ❌ Tidak |
| Ekspor Excel (.xls) | ✅ Ya (Lengkap) | ✅ Ya (Operasional) |
| **Kas (30%) & Bonus (10%)** | ✅ **Terlihat** | ❌ **Disembunyikan** |
| **📈 Grafik Tren Omset & Hasil** | ✅ **Terlihat** | ❌ **Disembunyikan** |
| Hapus Transaksi & Reset Data | ✅ Ya | ❌ Tidak |

---

## ✨ 4. Fitur-Fitur Utama

### 📋 A. Riwayat Buku Toko (3 Tampilan dalam 1 Bar Terpadu)
- Menyatukan riwayat harian dan ringkasan akumulasi periode ke dalam satu wadah kartu yang praktis dan efisien.
- **Pilihan Tampilan (Tabs Segmented):**
  - **`📅 Harian`** : Menampilkan daftar rincian setiap transaksi harian toko secara kronologis.
  - **`🗓️ Mingguan`** : Menampilkan ringkasan akumulasi per minggu (Senin s/d Minggu).
  - **`📆 Bulanan`** : Menampilkan ringkasan akumulasi per bulan kalender.
- **Tombol Panah Sembunyikan/Tampilkan (`▲` / `▼`):**
  - Menyembunyikan atau membuka seluruh tabel riwayat untuk tampilan yang lebih ringkas.
  - Pilihan status disimpan di browser secara otomatis.

### 📝 B. Kolom Catatan / Keterangan Transaksi
- Input transaksi dilengkapi kolom **Catatan** untuk mencatat keterangan belanja inventaris, servis, atau catatan harian lainnya.
- Tersimpan permanen di database SQLite dan disertakan dalam ekspor file Excel.

### 📈 C. Grafik Tren Omset & Hasil (Khusus Superadmin)
- Visualisasi grafik garis (*Line Chart*) interaktif berbasis Chart.js lokal (bekerja 100% offline).
- Membandingkan tren harian antara **Omset** dan **Hasil Bersih**.
- Otomatis disembunyikan saat pengguna login sebagai **Admin**.

### 🔔 D. Notifikasi Toast Sinkronisasi Antar Perangkat
- Sistem *live sync* otomatis memunculkan notifikasi banner (*Toast*) di pojok kanan atas saat ada perubahan data dari perangkat lain di jaringan LAN.

---

## 🗄️ 5. Database SQLite & Auto-Backup
- **Database SQLite (`pembukuan.db`):** Seluruh data tersimpan secara aman dan terpusat di SQLite.
- **Auto-Backup JSON:** Snapshot otomatis tersimpan di folder **`backup/`** setiap kali transaksi disimpan.
- **Fitur Restore:** Pemulihan database dapat dilakukan melalui menu Pengaturan (`⚙️`).
- **Ekspor Excel (.xls):** Tombol **Export (.xls)** langsung mengunduh file laporan dan mencadangkannya di folder `backup/`.
