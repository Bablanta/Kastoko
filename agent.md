# Panduan & Aturan AI Agent (KasToko)

Dokumen ini berisi aturan baku bagi AI Agent dalam mengembangkan, memodifikasi, dan mengeksekusi kode pada proyek **KasToko**.

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

## ⚙️ Aturan Operasional & Deployment
1. **Lokal First**: Selalu uji perubahan pada environment lokal (`http://localhost:8080`) sebelum melakukan deploy ke server Ubuntu (`192.168.1.8`).
2. **Deploy Terukur**: Jangan deploy ke server Ubuntu kecuali jika diinstruksikan oleh pengguna.
3. **Gunakan Wadah `tools/`**: Untuk utilitas seperti deploy, backup, dan inspeksi database, gunakan skrip yang telah distandardisasi di dalam folder `tools/` (misal: `tools/deploy_manager.py`, `tools/db_backup.py`, `tools/db_inspect.py`).
