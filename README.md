# 📊 Panduan Penggunaan & Dokumentasi Autocash

Aplikasi **Autocash** adalah aplikasi pembukuan toko modern berbasis web (HTML5, CSS3, JavaScript) dengan backend Python (`server.py`) dan database **SQLite (`pembukuan.db`)** yang mendukung sinkronisasi data real-time antar perangkat dalam jaringan lokal, pembagian hak akses (Superadmin & Admin), visualisasi grafik omset & hasil, riwayat buku toko terpadu (Harian, Mingguan, Bulanan), serta pencadangan database otomatis.

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
| **🗑️ Clear Data Servis (Reset No. Nota ke 001)** | ✅ **Ya (Khusus Superadmin)** | ❌ **Disembunyikan** |

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

### 🔧 E. Dashboard Servis & Reparasi Unit (Fitur Baru)
- **Navigasi Tab Terpadu:** Beralih instan antara **📊 Pembukuan Keuangan** dan **🔧 Dashboard Servis** dengan penghitung tiket aktif otomatis.
- **Pendaftaran & Input Servis Lengkap:**
  - **Data Pelanggan:** Nama Pelanggan & No. HP (WhatsApp).
  - **Auto-Save Data Pelanggan:** Pelanggan baru otomatis tersimpan ke master database pelanggan SQLite.
  - **Auto-Complete Pelanggan:** Mengetik nama atau nomor HP lama otomatis mengisi data pelanggan secara cerdas.
  - **Status Servis:** Pilihan status pengerjaan (*Baru*, *Instan*, *Sedang Dikerjakan*, *Selesai*, *Sudah Diambil*, *Batal*).
  - **Menu Servis:** Pilihan layanan (*Diagnosa*, *Servis Instan*, *Perbaikan Ringan*, *Ganti Sparepart*, *Servis Berat*).
  - **Data Unit / Perangkat:** Jenis perangkat (*Smartphone/HP*, *Laptop*, *PC*, *Tablet*, dll), Merk/Model, Keluhan Pelanggan, dan Catatan Teknisi.
  - **Estimasi Biaya & Tanggal Masuk.**
- **Antrean & Riwayat Servis:**
  - Filter pencarian cepat (Nama, No HP, Kode Servis, Merk/Model, Keluhan).
  - Filter tab status (*Semua*, *Baru*, *Instan*, *Diproses*, *Selesai*, *Diambil*).
  - Shortcut WhatsApp langsung ke nomor pelanggan untuk update pengerjaan.
  - Tombol ganti status cepat (*Baru* -> *Diproses* -> *Selesai* -> *Diambil*).
- **🖨️ Cetak Nota Tanda Terima:**
  - Pratinjau nota tanda terima profesional lengkap dengan rincian unit, keluhan, estimasi biaya, dan kolom tanda tangan pelanggan & teknisi yang siap dicetak ke printer biasa maupun thermal.

### 🖨️ F. Dual Thermal Printer & Fitur "Print All"
- **Printer 1 (Nota/Struk):** Mendukung ukuran kertas 58mm (POS-58 Mini) dan 80mm (POS-80 Standar).
- **Printer 2 (Label Stiker Unit):** Mendukung stiker 40x20mm, 40x30mm, dan 50x30mm untuk ditempel pada unit pelanggan.
- **Tombol `Print All`:** Mencetak nota dan label stiker unit secara bergiliran otomatis dengan jeda delay yang dapat diatur di menu Pengaturan.

### 💬 G. Integrasi WhatsApp Desktop & Notifikasi Gambar Nota
- **Direct WhatsApp Desktop:** Menggunakan protokol `whatsapp://send` langsung membuka aplikasi WhatsApp di Windows tanpa browser.
- **Nota Format Gambar (1-Klik via Clipboard):** Nota dirender menjadi gambar PNG resolusi tinggi secara offline dan otomatis disalin ke Clipboard Windows (`Ctrl + V` di WhatsApp).
- **Otomasi Servis Baru:** Setiap menyimpan servis baru berstatus "Baru", popup nota dan WhatsApp Desktop otomatis terbuka.
- **Unduh Manual PNG:** Tombol "📥 Unduh PNG" untuk menyimpan arsip file gambar ke komputer.

### 🗑️ H. Clear Data Servis & Reset Nomor Nota (Khusus Superadmin)
- **Reset Urutan Nota:** Mengembalikan urutan nomor tiket dan nota servis kembali ke awal (`001`), misal: `SRV-YYYYMMDD-001`.
- **Proteksi Akses:** Tombol hanya tampil untuk role Superadmin; disembunyikan sepenuhnya untuk Admin biasa.
- **Auto-Backup & Konfirmasi:** Dilengkapi modal peringatan dengan opsi Yes/No serta pembuatan file cadangan JSON otomatis di folder `backup/` sebelum data dibersihkan.

### ⚡ I. Direct Raw Thermal Printing (0% Dialog Windows)
- **Bypass Windows Print Dialog:** Menggunakan pustaka standard CPython `ctypes.WinDLL("winspool.drv")` (`printer_service.py`) untuk mengirim byte raw langsung ke printer via spooler `RAW`. Kertas langsung tercetak dalam hitungan milidetik tanpa jendela konfirmasi print peramban.
- **Hasil Cetak Pekat & Timbul (Heating Density):** Fitur pemanasan ganda (*Double-Strike / Emphasize*) hardware thermal untuk menghasilkan teks hitam pekat, tajam, dan timbul.
- **Dukungan Multi-Protokol:**
  - **Printer 1 (Nota 58mm / 80mm):** Protokol native **ESC/POS** dengan format kolom otomatis (32 kolom untuk 58mm, 48 kolom untuk 80mm) dan perataan tengah/kiri/kanan yang proporsional.
  - **Printer 2 (Label Stiker):** Protokol native **TSPL** dengan pembacaan sensor gap presisi agar stiker tercetak pas di tengah dan tidak selip.
- **Pendeteksian Printer Otomatis:** Menemukan printer yang terpasang di Windows (misal: `POS-58( USB )` & `80Label Printer ( USB )`) lengkap dengan tombol uji coba langsung di Pengaturan.

---

## 🗄️ 5. Database SQLite & Auto-Backup
- **Database SQLite (`pembukuan.db`):** Seluruh data tersimpan secara aman dan terpusat di SQLite.
- **Auto-Backup JSON:** Snapshot otomatis tersimpan di folder **`backup/`** setiap kali transaksi disimpan.
- **Fitur Restore:** Pemulihan database dapat dilakukan melalui menu Pengaturan (`⚙️`).
- **Ekspor Excel (.xls):** Tombol **Export (.xls)** langsung mengunduh file laporan dan mencadangkannya di folder `backup/`.

---

## 🚀 6. Cara Deploy & Sinkronisasi ke Server Ubuntu (192.168.1.8)

Untuk memperbarui server Ubuntu di `192.168.1.8`, kini cukup menggunakan **1 file tunggal**:
👉 **`deploy_ke_ubuntu.bat`** (klik ganda).

Skrip akan menampilkan menu interaktif:
1. **`[1] Update Lengkap: Kode Fitur + Database Pembukuan (Default / Rekomendasi)`**
   - Mentransfer file-file kode terbaru (`index.html`, `server.py`, `style.css`, dll).
   - Menyinkronkan database pembukuan terbaru (`pembukuan.db`) dari PC ke Ubuntu, dengan backup otomatis sebelum ditimpa.
   - Me-restart proses PM2 di Ubuntu dalam ~3 detik.
2. **`[2] Update Kode & Fitur Saja`**
   - Hanya memperbarui tampilan dan logika program tanpa mengubah database server (database server dipertahankan).
3. **`[3] Ambil Database dari Server Ubuntu ke PC Lokal`**
   - Menarik data transaksi kasir terbaru dari Ubuntu ke PC (misal setelah toko tutup).
4. **`[4] Push ke GitHub + Update Server Ubuntu`**
   - Mendorong (*push*) commit ke GitHub sekaligus memperbarui server Ubuntu.
