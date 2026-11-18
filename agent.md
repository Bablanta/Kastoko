# Panduan & Aturan AI Agent (KasToko)

Dokumen ini berisi aturan baku dan ringkasan konteks bagi AI Agent dalam mengembangkan, memodifikasi, dan mengeksekusi kode pada proyek **KasToko**.

---

## ⚡ Ringkasan Cepat Konteks Proyek (Executive Context for New Agents)
* **Aplikasi**: KasToko (Autocash) - Kasir & Servis Toko v0.0.10.
* **Fitur Terakhir**: **Master Kas** (4 Pos Kas: Aset 30%, Owner 30%, Investor 30%, Bonus 10% sinkron 100% dengan Total Hasil Toko).
* **Arsitektur**: Frontend [index.html](file:///E:/KasToko/index.html), Styling [style.css](file:///E:/KasToko/style.css), Backend [server.py](file:///E:/KasToko/server.py), Database `pembukuan.db` (SQLite).
* **Target Server**: Ubuntu Server `http://192.168.1.8:8080` (SSH: `bablanta@192.168.1.8`).
* **Deploy Command**: `python tools/deploy_manager.py code` (HANYA deploy file kode, **dilarang menimpa pembukuan.db di server**).
* **Detail Lengkap**: Baca [PROJECT_HANDOFF.md](file:///E:/KasToko/PROJECT_HANDOFF.md) untuk rincian serah terima konteks lengkap.

---

## 📌 Aturan Pokok Eksekusi

### 1. Jangan Terlalu Banyak Icon Baru
- **Desain Minimalis & Rapi**: Hindari menambahkan ikon atau emoji baru secara berlebihan pada tombol, kartu, tabel, maupun judul menu.
- **Konsistensi Simbol**: Gunakan kembali set ikon yang sudah ada dan terbukti konsisten dalam aplikasi (misal: 💾 Simpan, 🖨️ Cetak, 💰 Keuangan/Jasa, ⚙️ Pengaturan).
- **Hindari Polusi Visual**: Jangan gunakan beberapa ikon berbeda untuk fungsi yang setara. Prioritaskan kejelasan teks dan kerapian tata letak.

---

### 2. Jangan Menggunakan Lebih Banyak Warna Baru
- **Pertahankan Palet Warna Eksisting**: Selalu selaraskan dengan tema utama aplikasi (Hijau `#107c41`, aksen lembut `#a3cfbb` / `rgba(16, 124, 65, 0.12)`, latar putih `#ffffff`, dan variabel tema yang sudah ada seperti `var(--border-color)`, `var(--card-bg)`, dsb.).
- **Hindari Variasi Warna Liar**: Dilarang memperkenalkan warna atau gradasi baru yang mencolok tanpa instruksi eksplisit dari pengguna.
- **Keselarasan Visual**: Komponen baru atau modifikasi kartu/tombol harus menyatu secara alami dengan nuansa hijau-putih elegan yang sudah diterapkan.

---

### 3. Jangan Banyak Tanya Kecuali Permintaan Persetujuan
- **Eksekusi Langsung & Solutif**: Jika instruksi sudah jelas dan aman, langsung analisa, perbaiki, uji, dan selesaikan tanpa menanyakan hal-hal yang bersifat basa-basi atau sepele.
- **Kapan Boleh Bertanya**: HANYA ajukan pertanyaan atau berhenti untuk meminta konfirmasi jika:
  1. Melibatkan tindakan berisiko tinggi / destruktif (seperti menghapus data produksi, menimpa database `pembukuan.db` tanpa backup).
  2. Pengguna secara eksplisit memberikan instruksi: *"tunggu konfirmasi saya sebelum eksekusi"*.
  3. Ada dua pilihan arsitektural yang saling bertentangan secara mendasar dan tidak dapat diasumsikan dengan aman.

---

### 4. Dilarang Commit dan Deploy Tanpa Perintah Eksplisit
- **Jangan Commit & Push Tanpa Instruksi**: Dilarang melakukan `git commit` maupun `git push` sebelum pengguna secara tegas memberikan instruksi untuk commit.
- **Jangan Deploy Tanpa Perintah**: Dilarang menjalankan proses deploy ke server Ubuntu (`192.168.1.8`) sebelum ada instruksi langsung dari pengguna (misal: *"deploy"*). Seluruh pengujian wajib diselesaikan di server lokal komputer saja.

---

### 5. Dilarang Menimpa Database yang Ada di Server
- **Database Server Wajib Aman 100%**: Jangan pernah menimpa, menghapus, atau mengganti file database `pembukuan.db` yang berada di server Ubuntu dengan database lokal.
- **Gunakan Mode Code Saat Deploy**: Ketika pengguna memerintahkan deploy, selalu gunakan perintah mode kode: `python tools/deploy_manager.py code` (BUKAN mode `full`), sehingga transaksi kasir riil yang berjalan di server tidak akan pernah tertimpa.

---

### 6. Jangan Setiap Perubahan Di-update di `perubahan.md` (Tunggu Perintah)
- **Dilarang Otomatis Mengisi `perubahan.md`**: Jangan memperbarui atau menambahkan poin riwayat ke `perubahan.md` pada setiap perubahan kecil atau iterasi percobaan.
- **Tunggu Perintah Eksplisit**: HANYA perbarui dan catat ke `perubahan.md` jika pengguna secara tegas memberikan instruksi (contoh: *"simpan perubahan.md"* atau *"catat ke perubahan.md"*).

---

### 7. Selalu Lakukan Tes Print Langsung ke Hardware
- **Wajib Uji Cetak Fisik**: Setiap kali melakukan perubahan atau penyesuaian pada format, layout, font, atau margin nota (`#receiptPrintArea`) maupun label stiker, AI Agent wajib langsung melakukan tes cetak (*real print test*) ke printer fisik (`80Label Printer`) hingga data terkirim ke spooler.

---

### 8. Penomoran Versi di Pengaturan Aplikasi (Versioning)
- **Label Versi di Judul Pengaturan**: Judul menu Pengaturan Aplikasi wajib mencantumkan nomor versi (dimulai dari `Pengaturan Aplikasi v0.0.1`).
- **Peningkatan Versi Berkelanjutan (Incremental Versioning)**: Setiap kali ada perubahan fitur, perbaikan bug, atau pembaruan baru pada aplikasi, AI Agent wajib menaikkan nomor versi secara bertahap (`v0.0.1` -> `v0.0.2` -> `v0.0.3`, dan seterusnya) pada judul tersebut agar pengguna dapat melihat dengan jelas bahwa pembaruan sistem telah aktif dan termuat.

---

### 9. Gunakan Istilah Ringkas & Padat (Hindari Kata Terlalu Panjang)
- **Ringkas & Langsung pada Intinya**: Hindari penamaan tombol, opsi, atau teks antarmuka yang terlalu panjang dan bertele-tele.
- **Contoh Penerapan**:
  - Tombol `"Buka Manajemen Pengguna"` disederhanakan menjadi `"Akses User"`.
  - Opsi label `"40 x 20 mm (Mini Stiker - 5 Baris Identitas Murni)"` disederhanakan menjadi `"40 x 20 mm (Mini Stiker)"`.
  - Opsi nota `"80 mm (Standar Nota Kasir 80x100mm)"` disederhanakan menjadi `"80 mm (Standar Nota Kasir)"`.
- **Kenyamanan UI Kasir**: Teks yang ringkas membuat antarmuka kasir bersih, mudah dibaca cepat, dan tidak memakan ruang tombol.

---

## ⚙️ Aturan Operasional & Deployment
1. **Lokal First**: Selalu uji perubahan pada environment lokal (`http://localhost:8080`) terlebih dahulu.
2. **Dilarang Commit & Deploy Tanpa Perintah**: Jangan melakukan `git commit`, `git push`, maupun deploy ke server Ubuntu (`192.168.1.8`) sebelum ada perintah langsung dari pengguna.
3. **Jangan Pernah Menimpa Database Server**: Saat deploy diperintahkan, selalu gunakan mode aman `code` (`python tools/deploy_manager.py code`) untuk memastikan database `pembukuan.db` di server Ubuntu terlindungi sepenuhnya dari penimpaan data lokal.
4. **Jangan Update `perubahan.md` Tanpa Perintah**: Tunggu instruksi spesifik dari pengguna sebelum mencatat ke `perubahan.md`.
5. **Selalu Tes Print**: Jalankan verifikasi cetak langsung ke printer hardware setiap ada modifikasi nota.
6. **Gunakan Wadah `tools/`**: Untuk utilitas seperti deploy, backup, dan inspeksi database, gunakan skrip yang telah distandardisasi di dalam folder `tools/` (misal: `tools/deploy_manager.py`, `tools/db_backup.py`, `tools/db_inspect.py`).
7. **Pembaruan Versi Terus Menerus**: Selalu naikkan nomor versi pada judul "Pengaturan Aplikasi v..." secara berkala di setiap siklus perubahan berikutnya.
8. **Hindari Kata Terlalu Panjang**: Gunakan istilah UI yang ringkas, simpel, dan to the point (contoh: "Akses User" alih-alih "Buka Manajemen Pengguna").
