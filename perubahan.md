# Catatan Perubahan & Pembaruan Sistem (KasToko)

Dokumen ini mencatat seluruh riwayat perubahan, pembaruan antarmuka, penyesuaian logika cetak printer, penyelarasan nota WhatsApp, serta sinkronisasi database yang telah diterapkan pada aplikasi **KasToko**.

---

## 📅 Tanggal: 08 November 2026

### 1. 🛠️ Penyesuaian Formulir Penerimaan Servis Baru (Status Servis 3 Opsi)
Sesuai instruksi operasional penerimaan servis:
- **Penyederhanaan Status Servis**: Dropdown `Status Servis` (`#srvStatusServis`) pada menu **Formulir Penerimaan Servis Baru** kini secara ketat hanya menyajikan **3 opsi**:
  1. `🆕 Baru`
  2. `⚡ Instan`
  3. `🛡️ Claim Garansi`
- **Berlaku untuk Role Superadmin & Admin**: Akses pendaftaran dan perubahan status ini aktif penuh bagi pengguna dengan hak akses **Superadmin** maupun **Admin Kasir**.
- **Badge & Tab Khusus Garansi**:
  - Ditambahkan styling badge `.badge-claim` dengan warna *warm amber/orange* yang elegan dan kontras baik pada tema terang maupun tema gelap.
  - Ditambahkan tombol tab filter **`Garansi`** pada kartu antrean & riwayat servis sehingga admin dan superadmin dapat memfilter unit klaim garansi secara instan dalam 1 klik.
  - Dropdown ganti status cepat (*quick status*) pada tabel antrean servis untuk Superadmin dan Admin kini menyertakan opsi `Claim Garansi`.

---

### 2. 🖨️ Pemecahan Masalah Deteksi Printer di Domain Publik (`autocash.dhanzcell.my.id`)
**Analisis Akar Masalah (Root Cause):**
- Domain publik `autocash.dhanzcell.my.id` dijalankan dari server Ubuntu Linux di cloud via Cloudflare Tunnel.
- Di server Ubuntu Linux, modul driver Windows Spooler (`winspool.drv`) tidak tersedia, dan secara fisik kabel USB printer thermal kasir (`80Label Printer`) tertancap di PC Windows kasir di toko (`192.168.1.50`), bukan di mesin Linux Ubuntu.
- Sebelumnya, browser memanggil `/api/printers` langsung ke Linux, sehingga Linux mengembalikan daftar kosong `[]`. Selain itu, jika browser di HTTPS memanggil langsung ke IP lokal `http://127.0.0.1:8080`, browser Chromium memblokir request karena kebijakan *Private Network Access (PNA)* dan *Mixed Content*.

**Solusi & Arsitektur Jembatan Perangkat (Smart Hardware Bridge):**
1. **Endpoint Proxy & Caching (`/api/printers`)**:
   - Di file [server.py](file:///E:/KasToko/server.py), ketika server Linux menerima permintaan `/api/printers`, server secara otomatis menjembatani query ke PC Windows kasir (`http://192.168.1.50:8080/api/printers`) melalui jalur internal berkecepatan tinggi, lalu menyimpan daftar printer tersebut ke cache database `settings` (`cached_windows_printers`).
   - Domain publik `https://autocash.dhanzcell.my.id/api/printers` kini langsung merespons dengan daftar printer fisik Windows lengkap: `80Label Printer [CP001] (Default)`.
2. **Forwarding Cetak Hardware Otomatis**:
   - Seluruh endpoint cetak (`/api/print/receipt`, `/api/print/label`, `/api/print/both`, `/api/print/test`) yang dipanggil dari domain publik secara otomatis diteruskan (*forwarded*) oleh server Ubuntu ke PC Windows kasir toko.
   - Dengan demikian, kasir yang membuka aplikasi dari domain publik `autocash.dhanzcell.my.id` dapat mencetak nota langsung ke hardware thermal printer kasir secara *real-time* tanpa gangguan dialog browser.
3. **Penyempurnaan Frontend ([index.html](file:///E:/KasToko/index.html))**:
   - Dropdown perangkat printer kini secara otomatis memilih dan mempertahankan printer tersimpan (`80Label Printer`), sehingga dropdown tidak pernah kosong.
   - Telah diuji dan diverifikasi secara langsung via Headless Chrome pada `https://autocash.dhanzcell.my.id`.

---

## 📅 Tanggal: 07 November 2026

### 1. 🖨️ Pembaruan & Penyederhanaan Menu "Pengaturan Printer"
Telah dilakukan perapihan antarmuka pengaturan printer agar lebih bersih, mudah dipahami, dan langsung ke inti fungsi operasional kasir:
- **Judul Modal**: Diubah dari `"Pengaturan Dual Thermal Printer"` menjadi **`Pengaturan Printer`** (pada modal popup dan kartu menu pengaturan).
- **Penghapusan Subtitle Teknis**: Teks `"Direct Python RAW (ESC/POS & TSPL murni tanpa dialog Windows)"` telah dihapus dari header modal.
- **Label Printer Nota**: Diubah dari `"🧾 PRINTER 1: NOTA / STRUK"` menjadi **`🧾 PRINTER NOTA`**.
- **Label Printer Label**: Diubah dari `"🏷️ PRINTER 2: LABEL STIKER UNIT"` menjadi **`🏷️ PRINTER LABEL`**.
- **Label Koneksi**: Label `"Jalur Koneksi:"` disederhanakan menjadi **`Koneksi:`**.
- **Penyederhanaan Opsi Koneksi**: Opsi koneksi printer dipangkas menjadi **hanya 2 pilihan**:
  1. `USB`
  2. `Bluetooth`
- **Penyederhanaan Ukuran Kertas Nota**: Pilihan ukuran kertas nota pada menu pengaturan dan modal cetak nota disederhanakan menjadi **hanya 2 pilihan**:
  1. `58mm` (POS-58 Mini Thermal Kasir)
  2. `80mm` (POS-80 Standar Kasir & Label 78/80mm)
- **Label Perintah Label Barcode**: Diubah dari `"Bahasa Perintah Label Barcode:"` menjadi **`Perintah label barcode:`**, dengan opsi ringkas:
  1. `TSPL`
  2. `ESC/POS`
- **Pembersihan Menu Kepekatan (Density)**: Dropdown *Kepekatan Panas Thermal (Density)* telah dihapus dari tampilan antarmuka; sistem secara otomatis menerapkan parameter *Double-Strike High Density* terbaik di latar belakang agar hasil cetak selalu pekat dan timbul.
- **Penghapusan Tombol Konek BT**: Tombol `"📶 Konek BT"` pada bagian kartu printer nota telah dihapus.
- **Penghapusan Tombol Batal**: Tombol `"Batal"` pada bagian footer modal pengaturan printer telah dihapus, menyisakan tombol tunggal **`💾 Simpan Pengaturan Printer`** yang lebar penuh (*full-width*) dan tegas. (Modal tetap dapat ditutup melalui ikon silang `✕` pada sudut kanan atas header).

---

### 2. 🧾 Penyelarasan Isi Nota Tercetak & Notifikasi WhatsApp (100% Identik)
Seluruh struktur, penamaan label, dan urutan informasi antara **Nota Fisik Tercetak** (hardware printer TSPL/ESCPOS & pratinjau modal web) dengan **Pesan Teks WhatsApp** telah diselaraskan secara menyeluruh:

| Bagian Nota | Versi Nota Tercetak (Hardware & Modal) | Versi Pesan Notifikasi WhatsApp |
|---|---|---|
| **Header Toko** | Nama Toko, Alamat, Telp/WA | `*NAMA TOKO*`<br>Alamat<br>Telp/WA |
| **Subtitle Nota** | `TANDA TERIMA PENERIMAAN UNIT` (Masuk)<br>`NOTA PENGAMBILAN & KWITANSI` (Ambil) | `*TANDA TERIMA PENERIMAAN UNIT*` (Masuk)<br>`*NOTA PENGAMBILAN & KWITANSI*` (Ambil) |
| **Tanggal** | `Tanggal: YYYY-MM-DD` | `Tanggal: YYYY-MM-DD` |
| **Data Pelanggan** | `No. Tiket: <kode>`<br>`Pelanggan: <nama>`<br>`No. HP/WA: <no_hp>` | `*No. Tiket*    : <kode>`<br>`*Pelanggan*    : <nama>`<br>`*No. HP/WA*    : <no_hp>` |
| **Data Unit** | `Perangkat: <jenis>`<br>`Merk/Model: <model>`<br>`IMEI / SN: <imei>` *(jika ada)*<br>`Layanan: <layanan>`<br>`Keluhan: <keluhan>`<br>`Catatan Tek: <catatan>` *(jika ada)*<br>`Sparepart: <spp>` *(jika ada)* | `*Perangkat*    : <jenis>`<br>`*Merk/Model*   : <model>`<br>`*IMEI / SN*    : <imei>` *(jika ada)*<br>`*Layanan*      : <layanan>`<br>`*Keluhan*      : <keluhan>`<br>`*Catatan Tek*  : <catatan>` *(jika ada)*<br>`*Sparepart*    : <spp>` *(jika ada)* |
| **Biaya & Status (Masuk)** | `Estimasi Biaya: Rp <biaya>`<br>`Status Servis : <status>` | `*Estimasi Biaya*: Rp <biaya>`<br>`*Status Servis* : <status>` |
| **Biaya & Status (Ambil)** | `Total Biaya: Rp <biaya>`<br>`Status Bayar: LUNAS (Garansi X Hari)` | `*Total Biaya*  : Rp <biaya>`<br>`*Status Bayar* : LUNAS (Garansi X Hari)` |
| **Syarat & Ketentuan (Masuk)** | `* Simpan nota ini sebagai tanda bukti resmi saat mengambil unit.`<br>`* Kerusakan aksesoris tidak tercatat di luar tanggung jawab toko.` | `* Simpan nota ini sebagai tanda bukti resmi saat mengambil unit.`<br>`* Kerusakan aksesoris tidak tercatat di luar tanggung jawab toko.` |
| **Syarat & Ketentuan (Ambil)** | `* Unit telah diterima dalam kondisi baik & berfungsi normal.`<br>`* Simpan nota ini sebagai bukti sah garansi resmi servis.` | `* Unit telah diterima dalam kondisi baik & berfungsi normal.`<br>`* Simpan nota ini sebagai bukti sah garansi resmi servis.` |
| **Pelacakan Servis Online** | QR Code Scan & URL website | `🌐 *Lacak Status Servis Online:*`<br>`👉 https://lacak.dhanzcell.my.id/lacak?nota=<kode>` |

- **Penyempurnaan Pengiriman Gambar & Teks WA**: Fungsi `sendReceiptViaWhatsApp()` kini otomatis membaca nilai langsung dari input modal kasir (biaya akhir terkini, status lunas, pilihan masa garansi), sehingga pesan teks dan gambar nota yang tersalin ke clipboard dipastikan seratus persen sinkron.

---

### 3. 🌐 Kloning Penuh dari Server Ubuntu (192.168.1.8) ke PC Lokal
- Seluruh 29 file sistem produksi aktif berhasil disalin dari server `/home/bablanta/Kastoko/` ke PC lokal `E:\KasToko/`.
- File database utama `pembukuan.db` (49,152 bytes) berhasil dipulihkan dengan checksum MD5 identik 100% dan integritas `tools/db_inspect.py` terverifikasi **SEHAT (OK)**.
- Snapshot arsip lokal sebelum kloning tersimpan aman pada direktori:
  `E:\KasToko\backup\snapshot_local_pre_clone_20261107_221154/`.

---

### 4. ⚙️ Logika Cetak Adaptif di Backend (`server.py` & `printer_service.py`)
- Penanganan cerdas tipe printer berdasarkan pilihan ukuran kertas:
  - Jika ukuran kertas **`58mm`**: Sistem otomatis menggunakan protokol ESC/POS murni (32 kolom) agar pas dan tidak terpotong pada printer mini kasir.
  - Jika ukuran kertas **`80mm`**: Jika printer berupa printer label (seperti 80Label / XP-365B), sistem menggunakan bahasa TSPL presisi stiker label (78 x 98 mm); jika printer roll struk standar kasir, sistem menggunakan ESC/POS 80mm (48 kolom).

---

### 5. 🎨 Diferensiasi Format Nota Cetak Thermal vs Gambar WhatsApp & Margin Mentok Kiri

Menindaklanjuti permintaan pemisahan antara kebutuhan **pencetakan fisik kertas kasir** dengan **pengiriman gambar digital ke WhatsApp pelanggan**:

1. **Pembedaan Desain Nota Cetak vs Gambar WhatsApp**:
   - **Nota Cetak Fisik (`#receiptPrintArea`)**:
     - Dikhususkan untuk kertas printer kasir thermal (78x100mm, 80mm, 58mm).
     - Menggunakan tema hitam-putih kontras tinggi dot matrix.
     - Memuat kolom tanda tangan fisik pulpen: `Pelanggan` dan `Kasir / Teknisi`.
     - Memuat QR Code pelacakan dan syarat resmi klaim pengambilan/garansi.
   - **Gambar WhatsApp Digital (`#waReceiptCard`)**:
     - Dikhususkan sebagai **E-Tanda Terima Digital / E-Kwitansi WhatsApp** saat dibuka di layar smartphone pelanggan.
     - Mengusung tema hijau WhatsApp elegan (`#075e54` - `#128c7e`) beresolusi tinggi (tidak pecah).
     - Memiliki **Badge Status Kapsul** (misal: `🟢 Unit Diterima` atau `✅ UNIT DIAMBIL`).
     - Memiliki **Box Sorotan Biaya** beraksen hijau modern (misal: `Estimasi Biaya: Rp 200.000` atau `Total Biaya: Rp 200.000 (LUNAS)`).
     - **Tanpa tanda tangan fisik kosong**; digantikan oleh cap resmi `✓ E-Tanda Terima Resmi Digital - Diverifikasi Sistem`.
     - Tombol `"💬 Kirim WA (Gambar)"` otomatis me-render kartu E-Nota WhatsApp ini ke clipboard lalu membuka aplikasi WhatsApp.
   - **Fitur Tab Toggle Pratinjau di Modal**:
     - Kasir dapat beralih melihat langsung antara tab `🧾 Nota Cetak Thermal (78x100mm)` dan tab `💬 Gambar E-Nota WhatsApp` sebelum mencetak atau mengirim.

2. **Isi Nota yang Direkomendasikan (Ringkas & Esensial)**:
   - Data Pelanggan: `No. Tiket`, `Pelanggan`, `No. HP/WA`.
   - Data Unit: `Perangkat`, `Merk / Model`, `Keluhan` (italic).
   - Data Biaya & Status: `Estimasi Biaya` (Masuk) / `Total Biaya` (Ambil) & `Status Servis` / `Status Bayar`.
   - Baris teknis seperti `IMEI / SN`, `Layanan`, `Catatan Teknisi`, dan `Sparepart` otomatis disembunyikan jika kosong, dan otomatis tampil rapi jika terisi.

3. **Margin Mentok Kiri (Zero Left Offset)**:
   - Margin kertas thermal diatur `margin: 0; margin-left: 0;` dengan padding kiri minimal `0.5mm`.
   - Mengatasi masalah kertas printer kasir thermal yang sebelumnya terdorong ke tengah (`margin: 0 auto`) atau terpotong di tepi kanan.
   - Berlaku untuk tampilan pratinjau modal, `@media print`, dan percetakan iframe browser.

4. **Kop Toko: Logo Besar Rata Kiri & Identitas Usaha di Sebelahnya**:
   - Logo usaha ditampilkan di sisi kiri dengan ukuran besar dan proporsional (~46px x 46px).
   - Di sebelah kanan logo:
     - Nama Toko: Font tebal, warna hijau brand DHANZCELL SMARTPHONE (`#107c41`).
     - Alamat Usaha & Telp/WhatsApp Toko.
     - Subtitle Nota (`TANDA TERIMA PENERIMAAN UNIT` / `NOTA PENGAMBILAN & KWITANSI`).
     - Tanggal Transaksi.
   - Desain kop ini persis sesuai referensi visual yang dikirimkan.

---

### 6. 🧹 Penyederhanaan Antarmuka Modal "Cetak Nota" (Bebas Elemen Duplikat)

Untuk memaksimalkan kecepatan dan kenyamanan kasir saat mencetak atau mengirim nota, elemen-elemen informasi teknis dan tombol redundan telah dipangkas:

1. **Judul Modal**: Diubah dari `"🖨️ Cetak Nota Servis (Thermal 78 x 98 mm)"` menjadi ringkas: **`Cetak Nota`**.
2. **Penghapusan Menu "Ukuran Kertas"**: Dropdown pilihan ukuran kertas nota telah dihilangkan dari modal cetak karena konfigurasi ukuran kertas utama sudah tersentralisasi di menu Pengaturan Printer.
3. **Penghapusan Badge Printer**: Kartu/badge `"🟢 80Label Printer (USB) - Langsung Cetak Siap (0% Dialog Windows)"` telah dihapus.
4. **Penghapusan Banner Info 1-Klik**: Box informasi biru `"⚡ 1-Klik Langsung Cetak..."` telah dihapus sehingga pratinjau nota langsung terlihat tanpa terhalang banner.
5. **Penghapusan Tombol "Unduh PNG"**: Tombol unduh file gambar PNG telah dihilangkan dari baris tombol modal.
6. **Perubahan Teks Tombol WhatsApp**: Label tombol `"💬 Kirim WA (Gambar)"` diubah menjadi lebih ringkas: **`💬 Kirim WA`**.
7. **Penghapusan Tombol "Tutup"**: Tombol tutup di bagian footer tombol telah dihapus, menyisakan dua tombol aksi utama yang tegas: **`🖨️ Cetak Nota`** dan **`💬 Kirim WA`** (modal tetap dapat ditutup cepat melalui tombol silang `✕` di sudut kanan atas).

---

### 7. 🛠️ Perbaikan Kendala Masuk Aplikasi (Syntax Error di `index.html`)

Menindaklanjuti laporan pengguna bahwa aplikasi tidak bisa dibuka/masuk:
1. **Pemeriksaan Server Lokal**:
   - Backend `python server.py` dipastikan berjalan normal di `http://127.0.0.1:8080` (HTTP 200 OK untuk seluruh endpoint API).
2. **Investigasi Kendala Browser**:
   - Menggunakan inspeksi Headless Chrome DevTools Protocol (CDP) pada `index.html`, terdeteksi kendala:
     `SyntaxError: Unexpected token '}'` pada baris 4636 di dalam blok `<script>`.
   - Penyebab: Terdapat sisa kurung kurawal penutup ganda (`}`) dan baris tak lengkap setelah fungsi `downloadReceiptImage()`.
   - Dampak: Browser membatalkan eksekusi seluruh skrip JavaScript utama di halaman, sehingga fungsi autentikasi (`login()`, `checkAuth()`) dan interaksi UI tidak dapat berjalan saat tombol diklik.
3. **Tindakan Perbaikan**:
   - Menghapus kurung kurawal berlebih dan merapikan blok percabangan pada fungsi `downloadReceiptImage()` di `index.html`.
4. **Verifikasi Akhir**:
   - Evaluasi sintaks via `node --check` dan Chrome CDP terbukti bersih (**0 error / `Captured JS Errors: []`**).
   - Verifikasi sesi login lokal terbukti berhasil (`currentUser: admin`), data servis termuat normal (19 servis aktif), dan dashboard kasir dapat diakses penuh kembali.

---

### 8. 🗑️ Pembersihan Tombol Tab Toggle Pratinjau di Modal Cetak Nota

Menindaklanjuti permintaan pembersihan elemen pada modal Cetak Nota:
1. **Penghapusan Tombol/Card Toggle**:
   - Menghapus baris tombol toggle pratinjau:
     - `🧾 Nota Cetak Thermal (78x100mm)`
     - `💬 Gambar E-Nota WhatsApp`
2. **Dampak Tampilan**:
   - Tampilan modal kini langsung menyajikan pratinjau lembar nota fisik secara bersih dan lapang di bawah tab navigasi penerimaan/pengambilan unit.
   - Fitur kirim E-Nota WhatsApp tetap bekerja otomatis di latar belakang saat kasir menekan tombol **`💬 Kirim WA`**, sehingga kasir tidak perlu lagi mengganti mode pratinjau secara manual.

---

### 9. 🖨️ Penerapan Mode Cetak Grafis Bitmap Thermal (100% Identik Visual Layar)

Menindaklanjuti permintaan agar hasil cetak fisik pada printer thermal persis sama dengan tampilan pratinjau di layar:
1. **Latar Belakang & Masalah Sebelumnya**:
   - Sebelumnya, tombol `🖨️ Cetak Nota` mencetak menggunakan kode perintah teks mentah (*Direct RAW Character*).
   - Akibatnya, printer hanya mencetak huruf standar bawaan chip ROM printer tanpa logo gambar, kotak estimasi biaya menjadi kaku, dan tata letak tidak dapat meniru desain grafis di layar.
2. **Penerapan Mode Cetak Grafis Bitmap (Raster Image Printing)**:
   - **Frontend (`index.html`)**:
     - Fungsi `printReceiptOnly()` kini secara otomatis menangkap elemen pratinjau `#receiptPrintArea` menggunakan `html2canvas` skala 2x resolusi tinggi dan mengirimkan data grafisnya (`image_data`) ke endpoint `/api/print/receipt`.
   - **Backend (`printer_service.py` & `server.py`)**:
     - Menambahkan fungsi baru `format_image_receipt()` berbasis library Python Pillow (`PIL`).
     - Gambar diolah menjadi monokrom 1-bit dengan binarisasi kontras tinggi (*high-contrast threshold* 195).
     - Untuk **Printer Label/80Label/XP-365B (TSPL)**: Dikemas ke dalam perintah raster `BITMAP 8,10,width_bytes,height_dots,0,...` dengan lebar cetak 608 dot (76 byte) dan margin pengaman 1mm agar pas di tengah kertas label 78x98 mm / 80 mm tanpa selip.
     - Untuk **Printer Kasir Roll (ESC/POS)**: Dikemas ke dalam perintah raster resmi `GS v 0` (lebar 384 dot untuk 58mm, 576 dot untuk 80mm).
3. **Hasil Akhir**:
   - Logo bergambar di sisi kiri tercetak jelas dan tajam.
   - Tata letak identitas toko, nomor tiket tebal, detail unit, keluhan italic, dan kotak garis putus-putus (*dashed box*) Estimasi Biaya tercetak **100% SAMA PERSIS** seperti di layar.
   - Kolom tanda tangan pelanggan/kasir dan QR Code pelacakan tercetak berdampingan secara rapi.
   - Tetap mencetak senyap secara instan (*silent print*) tanpa membuka jendela dialog cetak Windows.

---

### 10. 🎨 Penyempurnaan Tampilan Nama Toko, Pratinjau WhatsApp & Otorisasi Cetak Role Teknisi

Menindaklanjuti permintaan pembaruan antarmuka dan hak akses:
1. **Nama Toko Warna Putih Border Hitam**:
   - Judul/nama toko pada kop nota fisik (`#rStoreTitle`), kartu WhatsApp (`#waStoreTitle`), dan lembar cetak disetel dengan gaya tipografi tegas:
     - Warna isi huruf: Putih solid (`#ffffff`).
     - Garis tepi / outline teks: Hitam solid (`-webkit-text-stroke: 1.2px #000000` dan `text-shadow` multi-arah hitam).
   - Tampilan nama toko tetap sangat kontras, terbaca jelas, dan estetik baik di layar monitor, pada gambar kartu E-Nota, maupun hasil raster printer thermal.

2. **Jendela Pratinjau Gambar & Tombol `[OK]` Setelah Klik "Kirim WA"**:
   - Menambahkan modal baru `#waImagePreviewModal` yang otomatis muncul setelah kasir mengklik tombol **`💬 Kirim WA`**.
   - Modal menampilkan gambar kartu E-Nota WhatsApp yang baru saja dihasilkan dan tersalin ke clipboard.
   - Dilengkapi tombol konfirmasi **`[OK]`** berwarna hijau khas WhatsApp.
   - Saat kasir menekan tombol **`[OK]`**, modal pratinjau tertutup secara mulus dan aplikasi langsung membuka WhatsApp tujuan pelanggan lengkap dengan draf pesan tanda terima resmi.

3. **Penghapusan Icon Cetak Nota (`🖨️`) untuk Role Teknisi**:
   - Pada baris data tabel servis (`#serviceTableBody`), tombol/icon cetak nota (`🖨️`) kini tidak ditampilkan untuk akun dengan role **`teknisi`** (hanya tombol ubah status dan tombol detail yang tersedia).
   - Pada modal jendela detail servis (`#serviceDetailModal`), tombol **`🖨️ Cetak Nota`** (`#dtlBtnPrintReceipt`) otomatis disembunyikan jika akun yang sedang masuk adalah role **`teknisi`**.
   - Hak cetak fisik nota servis difokuskan khusus untuk role **Admin Kasir** dan **Superadmin**.

---

### 11. 📐 Penyesuaian Margin Cetak Thermal Mentok Kiri (Anti-Terpotong di Ujung Kanan)

Menindaklanjuti laporan pengguna bahwa margin cetakan nota terpotong di ujung kanan:
1. **Analisis Penyebab**:
   - Sebelumnya, perintah cetak grafis TSPL menggunakan offset horizontal `BITMAP 8,10,...` (geser 8 dot / 1 mm ke kanan) dengan lebar target `608 dots` (76 mm).
   - Fisik *printhead* printer thermal 80mm/78mm (seperti 80Label / XP-365B) umumnya memiliki batas pemanas efektif selebar **72 mm (576 dots)**.
   - Akibat pergeseran dan lebar yang melebihi 576 dots tersebut, teks di ujung kanan (seperti digit akhir nominal biaya, nomor tiket, atau tepi QR code) terpotong oleh batas fisik printhead.

2. **Perbaikan Format Bitmap & Koordinat TSPL**:
   - **Offset X = 0 Dots (Mentok Kiri 100%)**:
     - Perintah raster diubah menjadi `BITMAP 0,8,{w_bytes},{target_h},0,...` sehingga hasil cetak menempel rapat ke batas paling kiri lembar kertas (*zero left margin*).
   - **Lebar Target 560 Dots (70 mm / 70 Bytes)**:
     - Lebar gambar disesuaikan secara proporsional ke 560 dots (70 mm).
     - Menjamin seluruh teks, tabel informasi, kotak estimasi biaya, kolom tanda tangan, dan QR code pelacakan berada aman di dalam bidang cetak 72 mm tanpa ada karakter yang terpotong di tepi kanan.
   - **Penyesuaian CSS Nota Fisik (`style.css`)**:
     - `.receipt-paper-80100` disetel `width: 70mm; max-width: 72mm; margin: 0 !important; margin-left: 0 !important; padding: 1.5mm 1mm 1.5mm 0mm !important;`.
     - Proporsi kolom label (35%) dan isi nilai (65%) dipadatkan agar rata kanan tidak menabrak batas kertas.

3. **Uji Coba Cetak Fisik Hardware Langsung**:
   - Dilakukan eksekusi cetak langsung ke printer fisik **`80Label Printer`**:
     - **Uji Cetak Nota Servis Real (`/api/print/receipt`)**: Data nota servis aktif (`SRV-20261107-004`) telah dirender melalui `html2canvas` dan berhasil dikirim langsung ke hardware printer thermal.
     - **Uji Cetak Halaman Tes Hardware (`/api/print/test`)**: Berhasil dikirim dengan format mentok kiri tanpa antrean (*0 pending jobs* di Windows Print Spooler).

---

### 12. 🐛 Perbaikan Bug Rentang Waktu Mingguan & Pembersihan Footer Modal Pengaturan Umum

Menindaklanjuti temuan kendala dari pengguna:
1. **Perbaikan Penghitungan Rentang Waktu Mingguan & Bulanan**:
   - **Kendala**: Pada tabel Rekapitulasi Mingguan (`renderWeekly`) dan Bulanan (`renderMonthly`), kolom kedua (`Hari / Transaksi`) sebelumnya salah menampilkan total baris transaksi (`item.count++`) sebagai satuan hari. Contohnya pada rentang `2 Nov - 8 Nov 2026` yang memiliki 23 transaksi tercatat keliru sebagai `23 hari`.
   - **Solusi**: Diperbaiki dengan mengumpulkan tanggal transaksi unik (`daysSet[t.tanggal] = true`) pada tiap blok minggu dan bulan.
   - **Hasil**: Kini sistem menghitung jumlah hari aktif transaksi secara presisi. Pada baris `2 Nov - 8 Nov 2026` (transaksi berlangsung dari Senin 2 Nov s/d Sabtu 7 Nov), kolom kini menampilkan tepat **`6 hari`** sesuai operasional mingguan toko.

2. **Penghapusan Tombol "✕ Tutup Pengaturan" pada Modal Pengaturan Umum**:
   - Menghapus elemen footer modal `.settings-modal-footer` yang memuat tombol besar `"✕ Tutup Pengaturan"` pada `#settingsModal`.
   - Tampilan jendela pengaturan umum menjadi lebih bersih, ringkas, dan leluasa tanpa tombol penutup ganda.
   - Pengguna tetap dapat menutup jendela pengaturan umum dengan mudah melalui tombol `✕` di sudut kanan atas modal.

---

### 13. 🚀 Deploy dan Sinkronisasi ke Server Ubuntu (192.168.1.8)

Menindaklanjuti instruksi deploy ke server:
1. **Pembaruan Kode**:
   - Seluruh pembaruan kode aplikasi terbaru (`index.html`, `style.css`, `printer_service.py`, `server.py`, `perubahan.md`, dan `Readme.md`) telah diunggah ke direktori `/home/bablanta/Kastoko` di server Ubuntu melalui SFTP.
2. **Keamanan Database Server**:
   - Dijalankan dalam mode `CODE` (non-destructive) sehingga database transaksi live di server Ubuntu (`pembukuan.db`) tetap aman tanpa risiko tertimpa.
3. **Restart Service & Pengujian Live**:
   - Layanan KasToko di Ubuntu berhasil direstart melalui PM2 (`npx pm2 restart Kastoko`).
   - Verifikasi melalui Chrome Headless ke `http://192.168.1.8:8080` memastikan:
     - Tabel mingguan `2 Nov - 8 Nov 2026` tampil tepat **`6 hari`**.
     - Modal Pengaturan Umum bersih tanpa tombol `"✕ Tutup Pengaturan"`.
     - Seluruh endpoint API servis dan pembukuan merespons normal (HTTP 200 OK).

---

### 14. 🔠 Kapitalisasi Huruf Awal Otomatis (Title Case), Kunci Nama Pelanggan Anti-"User", & Isolasi Akun Teknisi

Menindaklanjuti permintaan terbaru:
1. **Input Data Manual Selalu Berawalan Huruf Besar (Title Case)**:
   - **Frontend**: Menambahkan helper global `capitalizeWords(str)` dan `applyAutoCapitalize(el)` dengan event listener terdelegasi pada level `document` untuk event `input` dan `blur`.
   - **Proteksi Kursor**: Menjaga posisi kursor teks (`selectionStart` & `selectionEnd`) saat mengetik sehingga pengetikan tetap mulus tanpa bug cursor jumping ke ujung baris.
   - **Visual CSS**: Menambahkan rule CSS `text-transform: capitalize;` pada form input penerimaan servis (`#srvNamaPelanggan`, `#srvMerkModel`, `#srvKeluhan`, `#srvCatatanTeknisi`, dll), transaksi buku kas, dan modal teknisi/kasir.
   - **Backend**: Menambahkan helper `capitalize_words()` di `server.py` sebelum proses penyimpanan data servis, pelanggan, dan transaksi buku kas sehingga data yang tersimpan di database dan dicetak ke nota thermal selalu berawalan huruf besar rapi.

2. **Kunci Nama Pelanggan Anti-"User"**:
   - **Frontend**: Validasi otomatis saat mengetik nama pelanggan. Jika mengandung kata `"user"` (case-insensitive), kotak peringatan merah muncul seketika di bawah input dan border input berubah menjadi merah.
   - **Blokir Submit**: Pada fungsi `saveServiceOrder()`, jika nama pelanggan mengandung kata `"user"`, penyimpanan dibatalkan dan memunculkan notifikasi peringatan.
   - **Backend**: Validasi ketat regex `re.search(r'user', nama, re.IGNORECASE)` di `auto_save_customer()`, `/api/services` POST, dan `/api/customers` POST.

3. **Penyesuaian Akses Riwayat Servis & Estimasi Biaya Teknisi**:
   - **Semua Riwayat Servis Tetap Tampil**: Akun teknisi tetap dapat melihat semua riwayat tiket servis toko di antrean utama dan dapat membuka modal detail untuk melihat kerusakan/tipe perangkat.
   - **Harga Tetap Tampil Sebelum Diambil**: Pada tiket yang belum ada teknisinya (`unassigned`), nominal estimasi biaya pengerjaan **tetap ditampilkan** (contoh: `Rp 150.000`) agar teknisi mengetahui nilai pekerjaan sebelum mengklik *"✋ Ambil Servis"*.
   - **Harga Dikerjakan Teknisi Lain Dirahasiakan**: Ketika tiket sedang/telah dikerjakan oleh teknisi lain, estimasi biaya disembunyikan/tidak tampak (**`🔒 Dirahasiakan`**) baik di tabel antrean maupun di modal detail, dan nominalnya dimasking menjadi `0` di API backend.
   - **Tiket Milik Sendiri**: Estimasi biaya dan biaya akhir pengerjaan servis miliknya sendiri tetap ditampilkan normal.

---

### 15. 🚀 Deploy & Sinkronisasi Live ke Server Ubuntu (autocash.dhanzcell.my.id)

1. **Deploy Kode Sebelumnya**:
   - Pembaruan awal di-deploy ke server Ubuntu dan diverifikasi.
2. **Catatan Sesuai Permintaan Pengguna**:
   - Sesuai instruksi *"jangan deploy dulu"*, pembaruan penyesuaian privasi teknisi ini diterapkan dan diverifikasi secara khusus di lingkungan **lokal kasir (`http://127.0.0.1:8080`)** tanpa melakukan deploy ke server Ubuntu.

---

### 16. 🎨 Pembaruan Format & Desain Cetak Nota Thermal Modern (High-Tech Tech Receipt)

Menindaklanjuti instruksi untuk mengubah hasil cetak printer kasir dan memberikan rekomendasi format yang lebih modern, elegan, profesional, dan tajam:
1. **Penerapan 5 Pilar Desain Nota Modern**:
   - **Kop Toko & Identitas Brand Solid**: Mengganti gaya font berlubang (*hollow stroke*) yang rawan pudar di kertas thermal dengan tipografi sans-serif bold solid hitam pekat, kontak alamat dan WhatsApp satu baris padat berpemisah bullet (`Jl. Cibaduyut No. 92 • WA: 0852-2300-2300`), serta badge kapsul hitam solid (*inverted pill badge*) `✦ TANDA TERIMA PENERIMAAN UNIT ✦` yang tercetak kontras 100% laser-sharp.
   - **Hero Ticket & Time Banner**: Nomor tiket ditempatkan pada kartu berbingkai micro-border eksklusif (`TIKET #SRV-20261107-004`) bersebelahan dengan tanggal dan jam masuk unit secara proporsional.
   - **Modern Spec-Sheet Grid**: Memisahkan blok data pelanggan dan spesifikasi teknis perangkat secara terstruktur, dilengkapi **Issue Highlight Box** berlatar abu-abu halus dengan aksen garis hitam vertikal di sisi kiri untuk membedakan keluhan pelanggan dan catatan teknisi.
   - **Highlight Box Biaya & Status**: Diberi bingkai solid 1.5px dengan nominal biaya ekstra besar (`Rp 150.000`, font-size: 13.5px, font-weight: 900) dan pil status hitam solid (`[BARU]` atau `[LUNAS (Garansi X Hari)]`).
   - **Dual Footer Minimalis**: Mengganti titik-titik tanda tangan jadul `( ....... )` dengan garis bawah horizontal minimalis rapi (`____________________`) lengkap dengan nama pelanggan tercetak rapi di bawahnya, berdampingan dengan QR Code pelacakan status servis online.
   - **Presisi Dimensi Kertas**: Lebar optimal 70 mm (560 dots) dan tinggi ~88-92 mm (maksimal 736 dots) pas 100% pada stiker label thermal `78 x 98 mm` tanpa melompat ke lembar stiker kedua.

2. **Penyelarasan Kode Frontend & Backend**:
   - Template nota fisik di [index.html](file:///E:/KasToko/index.html) (`#receiptPrintArea`) dan styling di [style.css](file:///E:/KasToko/style.css) (`.receipt-paper-80100`).
   - Logika data binding di [index.html](file:///E:/KasToko/index.html) (`populateReceipt()` dan `updateReceiptStoreHeader()`).
   - Fallback TSPL native di [printer_service.py](file:///E:/KasToko/printer_service.py) (`format_tspl_receipt()`).

3. **Verifikasi & Uji Cetak Hardware Fisik**:
   - Evaluasi rendering via Headless Chrome DevTools Protocol terverifikasi rapi dan proporsional.
   - Uji cetak langsung tiket riil `#SRV-20261107-004` berhasil dieksekusi ke hardware printer **`80Label Printer`** melalui Windows Print Spooler dengan status 0 pending jobs.

---

### 17. 🧾 Format Nota Sederhana: Rata Atas, Rata Kiri & Teks Hitam Pekat

Sesuai arahan pengguna untuk membuat versi alternatif yang lebih sederhana, rata atas dan rata kiri, serta seluruh teks berwarna hitam pekat:
1. **Tata Letak Rata Atas & Kiri (Clean Left-Aligned)**:
   - **Header Kop Toko**: Logo di kiri atas, nama toko tebal rata kiri, alamat usaha dan nomor WhatsApp tersusun rapi di bawahnya secara rata kiri.
   - **Judul Nota & Timestamp**: `TANDA TERIMA PENERIMAAN UNIT` dan waktu transaksi rata kiri dengan garis pembatas hitam tegas.
   - **Tabel Rincian Data**: Menggunakan format tabular 2 kolom rapat kiri dengan titik dua sejajar (`No. Tiket : ...`, `Pelanggan : ...`, `Perangkat : ...`, `Keluhan : ...`).
   - **Kotak Biaya & Status**: Border minimalis hitam solid tanpa latar belakang berbayang, nominal biaya tebal di sisi kanan (`Rp 150.000`), dan status unit `BARU` (atau `LUNAS`).
   - **Footer Sederhana**: Catatan tanda bukti, kolom tanda tangan bergaris bawah minimalis, dan QR code pelacakan status di sisi kanan.

2. **Karakteristik Teks Hitam Pekat (100% Solid Black)**:
   - Seluruh teks, border, dan label menggunakan warna hitam murni (`#000000`).
   - Bebas dari teks abu-abu pudar atau badge blok hitam yang terlalu berat, menghasilkan pemanasan printhead thermal 203 DPI yang sangat tajam, bersih, kontras tinggi, dan mudah dibaca pelanggan.

3. **Penyelarasan & Uji Coba Lokal**:
   - Diterapkan pada [index.html](file:///E:/KasToko/index.html) (`#receiptPrintArea`), [style.css](file:///E:/KasToko/style.css) (`.receipt-paper-80100`), dan [printer_service.py](file:///E:/KasToko/printer_service.py).
   - Telah diuji cetak langsung ke printer hardware **`80Label Printer`** melalui Windows Print Spooler dengan status 0 pending jobs.
   - **Catatan**: Sesuai instruksi pengguna, perubahan ini **hanya aktif di lingkungan lokal PC kasir (`E:\KasToko`)** dan tidak di-deploy ke server Ubuntu.

---

*Dokumen ini akan terus diperbarui seiring berjalannya penyesuaian dan fitur baru pada sistem KasToko.*
