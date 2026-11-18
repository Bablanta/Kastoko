# Ringkasan Proyek & Serah Terima Konteks (Project Handoff)

> **Untuk AI Agent Baru**: Dokumen ini adalah panduan cepat agar Anda langsung memahami seluruh konteks aplikasi KasToko dalam 1 menit tanpa perlu membaca ribuan baris kode dari awal.

---

## 1. Identitas & Status Proyek Terkini
* **Nama Aplikasi**: **KasToko (Autocash)** - Sistem Kasir, Servis HP/Laptop, dan Pembukuan Toko.
* **Versi Aktif**: **v0.0.10** (November 2026).
* **Cabang Git**: `main` (commit sinkronisasi Master Kas).
* **Target Server Produksi**: Ubuntu Server di `http://192.168.1.8:8080` (SSH: `bablanta@192.168.1.8:/home/bablanta/Kastoko`).

---

## 2. Fitur Baru Terakhir yang Telah Selesai: "Master Kas"
Sistem tata kelola kas otomatis di modul **Pembukuan Kas** (khusus Superadmin & Admin):
1. **Formula Alokasi Otomatis (100% Sinkron dengan Total Hasil Toko)**:
   $$\text{Total Hasil Toko} = \text{Omset} - \text{SPP} - \text{Operasional Toko Umum} - \text{Jasa Teknisi}$$
   Total Hasil Toko ini secara realtime langsung dibagi ke **4 Pos Kas**:
   * 🏛️ **Kas Aset (30%)**: Alokasi aset & alat toko.
   * 👑 **Kas Owner (30%)**: Prive / hak bersih pemilik toko.
   * 💼 **Kas Investor (30%)**: Bagi hasil modal investor toko.
   * 🎁 **Kas Bonus (10%)**: Reward & bonus tim.
2. **Kontrol Pengeluaran ("Pakai Kas Mana")**:
   * Setiap input pengeluaran operasional di modal *Catat Operasional (Opp)* wajib memilih sumber pos kas (`umum`, `aset`, `owner`, `investor`, `bonus`).
   * Pengeluaran dari pos kas spesifik langsung memotong saldo pos kas yang bersangkutan.
3. **Database**:
   * Kolom `pos_kas TEXT DEFAULT 'umum'` pada tabel `transactions` di `pembukuan.db`.

---

## 3. Arsitektur File Utama
* **Frontend**: [index.html](file:///E:/KasToko/index.html) (Single Page Application dengan Vanilla JS murni, tabel transaksi, modal kasir & servis, kalkulasi keuangan).
* **Styling**: [style.css](file:///E:/KasToko/style.css) (CSS tema *dark & light luxury*, layout full-width responsif).
* **Backend**: [server.py](file:///E:/KasToko/server.py) (Python HTTP Server standar melayani REST API `/api/*` dan file statis).
* **Database**: `pembukuan.db` (SQLite lokal & SQLite server Ubuntu).
* **Tools**: Folder [tools/](file:///E:/KasToko/tools/) berisi skrip operasional:
  * `python tools/deploy_manager.py code`: **Wajib digunakan untuk deploy** (hanya kirim file kode, database server aman).
  * `python tools/db_backup.py`: Skrip backup otomatis SQLite & JSON.

---

## 4. SOP & Aturan Mati AI Agent (Wajib Dipatuhi)
1. **Dilarang Menimpa Database Server**: JANGAN PERNAH menimpa file `pembukuan.db` di server Ubuntu. Selalu deploy dengan mode `code`.
2. **Dilarang Commit & Deploy Tanpa Perintah**: Tunggu instruksi tegas dari pengguna sebelum melakukan `git commit`, `git push`, atau deploy.
3. **Desain Minimalis**: Jangan menambah ikon/emoji baru atau warna baru yang mencolok secara berlebihan. Pertahankan palet hijau elegan (`#107c41`).
4. **Langsung Eksekusi & Solutif**: Jangan banyak tanya hal sepele kecuali tindakan berisiko tinggi / konfirmasi persetujuan pengguna.
5. **Uji Print Fisik**: Setiap ada modifikasi struk/nota, selalu lakukan verifikasi cetak langsung ke printer hardware.
