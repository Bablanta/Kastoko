import http.server
import socketserver
import os
import json
import sqlite3
import datetime
import urllib.parse
import threading
import signal
import time

try:
    import printer_service
except Exception as e:
    printer_service = None
    print(f"[WARN] Module printer_service tidak dapat dimuat: {e}")

def get_store_settings_dict():
    """Mengambil setting toko & printer dari database pembukuan.db"""
    res = {
        "store_name": "AUTOCASH SERVIS",
        "store_address": "",
        "store_phone": "",
        "nota_paper_size": "58",
        "label_paper_size": "40x30",
        "nota_printer_name": "",
        "label_printer_name": "",
        "label_mode": "tspl",
        "print_density": "high",
        "print_delay_ms": 600
    }
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        for k, v in cursor.fetchall():
            res[k] = v
        conn.close()
    except Exception:
        pass
    return res

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(DIRECTORY, "pembukuan.db")
OLD_DATA_FILE = os.path.join(DIRECTORY, "transactions.json")
BACKUP_DIR = os.path.join(DIRECTORY, "backup")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabel transaksi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL,
            omset REAL DEFAULT 0,
            spp REAL DEFAULT 0,
            opp REAL DEFAULT 0,
            jasa REAL DEFAULT 0,
            hasil REAL DEFAULT 0,
            catatan TEXT DEFAULT ''
        )
    ''')
    
    # Tabel settings (untuk menyimpan kunci Opp Toko, dll secara permanen di server)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Tabel master data pelanggan (Auto-saved)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            no_hp TEXT NOT NULL,
            alamat TEXT DEFAULT '',
            total_servis INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabel tiket & antrean servis
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_servis TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            nama_pelanggan TEXT NOT NULL,
            no_hp TEXT NOT NULL,
            jenis_perangkat TEXT NOT NULL,
            merk_model TEXT NOT NULL,
            keluhan TEXT NOT NULL,
            catatan_teknisi TEXT DEFAULT '',
            menu_servis TEXT NOT NULL,
            status_servis TEXT DEFAULT 'Baru',
            estimasi_biaya REAL DEFAULT 0,
            biaya_akhir REAL DEFAULT 0,
            status_pembayaran TEXT DEFAULT 'Belum Bayar',
            tanggal_masuk TEXT NOT NULL,
            tanggal_selesai TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Migrasi kolom catatan jika tabel sudah ada dari versi sebelumnya
    cursor.execute("PRAGMA table_info(transactions)")
    cols = [col[1] for col in cursor.fetchall()]
    if "catatan" not in cols:
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN catatan TEXT DEFAULT ''")
            conn.commit()
            print("[INFO] Kolom 'catatan' berhasil ditambahkan ke tabel transactions.")
        except Exception as e:
            print(f"[WARNING] Gagal migrasi kolom catatan: {e}")
    if "service_id" not in cols:
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN service_id INTEGER DEFAULT NULL")
            conn.commit()
            print("[INFO] Kolom 'service_id' berhasil ditambahkan ke tabel transactions.")
        except Exception as e:
            print(f"[WARNING] Gagal migrasi kolom service_id: {e}")

    # Migrasi kolom sparepart & metode bayar pada services
    cursor.execute("PRAGMA table_info(services)")
    s_cols = [col[1] for col in cursor.fetchall()]
    if "sparepart_nama" not in s_cols:
        try:
            cursor.execute("ALTER TABLE services ADD COLUMN sparepart_nama TEXT DEFAULT ''")
            conn.commit()
        except Exception as e:
            print(f"[WARNING] Gagal migrasi sparepart_nama: {e}")
    if "sparepart_biaya" not in s_cols:
        try:
            cursor.execute("ALTER TABLE services ADD COLUMN sparepart_biaya REAL DEFAULT 0")
            conn.commit()
        except Exception as e:
            print(f"[WARNING] Gagal migrasi sparepart_biaya: {e}")
    if "metode_pembayaran" not in s_cols:
        try:
            cursor.execute("ALTER TABLE services ADD COLUMN metode_pembayaran TEXT DEFAULT 'Tunai'")
            conn.commit()
        except Exception as e:
            print(f"[WARNING] Gagal migrasi metode_pembayaran: {e}")

    # Migrasi otomatis dari transactions.json lama jika database masih kosong
    cursor.execute("SELECT COUNT(*) FROM transactions")
    count = cursor.fetchone()[0]
    if count == 0 and os.path.exists(OLD_DATA_FILE):
        try:
            with open(OLD_DATA_FILE, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                for t in old_data:
                    cursor.execute('''
                        INSERT INTO transactions (tanggal, omset, spp, opp, jasa, hasil, catatan)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        t.get('tanggal', ''),
                        float(t.get('omset', 0) or 0),
                        float(t.get('spp', 0) or 0),
                        float(t.get('opp', 0) or 0),
                        float(t.get('jasa', 0) or 0),
                        float(t.get('hasil', 0) or 0),
                        str(t.get('catatan', '') or '')
                    ))
            conn.commit()
            print("[INFO] Berhasil mengimpor data lama dari transactions.json ke pembukuan.db")
        except Exception as e:
            print(f"[WARNING] Gagal migrasi data lama: {e}")

    conn.close()

def generate_service_code(cursor):
    """Generate kode servis otomatis format: SRV-YYYYMMDD-001"""
    today_str = datetime.date.today().strftime("%Y%m%d")
    prefix = f"SRV-{today_str}-"
    cursor.execute("SELECT kode_servis FROM services WHERE kode_servis LIKE ? ORDER BY id DESC LIMIT 1", (f"{prefix}%",))
    row = cursor.fetchone()
    if row and row[0]:
        last_code = row[0]
        try:
            last_num = int(last_code.split("-")[-1])
            new_num = last_num + 1
        except Exception:
            new_num = 1
    else:
        new_num = 1
    return f"{prefix}{new_num:03d}"

def auto_save_customer(cursor, nama, no_hp, alamat=""):
    """Simpan atau perbarui data pelanggan otomatis ke tabel customers"""
    nama = nama.strip()
    no_hp = no_hp.strip()
    if not nama:
        return None
    cursor.execute("SELECT id, total_servis FROM customers WHERE (nama = ? AND no_hp = ?) OR (no_hp != '' AND no_hp = ?)", (nama, no_hp, no_hp))
    cust = cursor.fetchone()
    if cust:
        cust_id = cust[0]
        total = (cust[1] or 0) + 1
        cursor.execute("UPDATE customers SET nama = ?, no_hp = ?, total_servis = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (nama, no_hp, total, cust_id))
        return cust_id
    else:
        cursor.execute("INSERT INTO customers (nama, no_hp, alamat, total_servis) VALUES (?, ?, ?, 1)", (nama, no_hp, alamat))
        return cursor.lastrowid

init_db()

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/transactions":
            try:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT id, tanggal, omset, spp, opp, jasa, hasil, catatan, service_id FROM transactions ORDER BY id ASC")
                rows = cursor.fetchall()
                
                transactions = []
                for row in rows:
                    transactions.append({
                        "id": row["id"],
                        "tanggal": row["tanggal"],
                        "omset": float(row["omset"] or 0),
                        "spp": float(row["spp"] or 0),
                        "opp": float(row["opp"] or 0),
                        "jasa": float(row["jasa"] or 0),
                        "hasil": float(row["hasil"] or 0),
                        "catatan": row["catatan"] or "",
                        "service_id": row["service_id"] if "service_id" in row.keys() else None
                    })
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "transactions": transactions}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        elif path == "/api/settings":
            try:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT key, value FROM settings")
                rows = cursor.fetchall()
                
                settings = {}
                for row in rows:
                    settings[row["key"]] = row["value"]
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "settings": settings}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        elif path == "/api/backups":
            try:
                if not os.path.exists(BACKUP_DIR):
                    os.makedirs(BACKUP_DIR, exist_ok=True)
                
                files = []
                for f in os.listdir(BACKUP_DIR):
                    if f.endswith('.json'):
                        file_path = os.path.join(BACKUP_DIR, f)
                        files.append({
                            "filename": f,
                            "size": os.path.getsize(file_path),
                            "time": os.path.getmtime(file_path)
                        })
                files.sort(key=lambda x: x['time'], reverse=True)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "backups": files}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        elif path == "/api/logo":
            try:
                logo_path = os.path.join(DIRECTORY, "logo.ico")
                has_custom = os.path.exists(logo_path)
                mtime = int(os.path.getmtime(logo_path)) if has_custom else 0
                logo_url = f"/logo.ico?t={mtime}" if has_custom else "/default_logo.ico"

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "has_custom_logo": has_custom,
                    "logo_url": logo_url
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        elif path == "/api/services":
            try:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                status_filter = query.get('status', [None])[0]
                search_q = query.get('q', [None])[0]

                sql = "SELECT * FROM services"
                clauses = []
                args = []
                if status_filter and status_filter != 'Semua':
                    clauses.append("status_servis = ?")
                    args.append(status_filter)
                if search_q:
                    clauses.append("(nama_pelanggan LIKE ? OR no_hp LIKE ? OR merk_model LIKE ? OR kode_servis LIKE ? OR keluhan LIKE ?)")
                    q_like = f"%{search_q}%"
                    args.extend([q_like, q_like, q_like, q_like, q_like])
                if clauses:
                    sql += " WHERE " + " AND ".join(clauses)
                sql += " ORDER BY id DESC"

                cursor.execute(sql, args)
                rows = cursor.fetchall()
                services = [dict(row) for row in rows]
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "services": services}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        elif path == "/api/printers":
            try:
                printers = printer_service.get_installed_printers() if printer_service else []
                def_printer = printer_service.get_default_printer() if printer_service else None
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "printers": printers, "default": def_printer}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        elif path == "/api/customers":
            try:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                search_q = query.get('q', [None])[0]
                if search_q:
                    cursor.execute("SELECT * FROM customers WHERE nama LIKE ? OR no_hp LIKE ? ORDER BY total_servis DESC, nama ASC LIMIT 50", (f"%{search_q}%", f"%{search_q}%"))
                else:
                    cursor.execute("SELECT * FROM customers ORDER BY total_servis DESC, nama ASC LIMIT 100")
                rows = cursor.fetchall()
                customers = [dict(row) for row in rows]
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "customers": customers}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/transactions":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                transactions = data.get('transactions', [])

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                
                # Replace all transactions
                cursor.execute("DELETE FROM transactions")
                for t in transactions:
                    cursor.execute('''
                        INSERT INTO transactions (tanggal, omset, spp, opp, jasa, hasil, catatan, service_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        t.get('tanggal', ''),
                        float(t.get('omset', 0) or 0),
                        float(t.get('spp', 0) or 0),
                        float(t.get('opp', 0) or 0),
                        float(t.get('jasa', 0) or 0),
                        float(t.get('hasil', 0) or 0),
                        str(t.get('catatan', '') or ''),
                        t.get('service_id')
                    ))
                conn.commit()
                conn.close()

                # Buat file backup JSON snapshot otomatis di folder backup/
                if not os.path.exists(BACKUP_DIR):
                    os.makedirs(BACKUP_DIR, exist_ok=True)
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                backup_filename = f"db_backup_{timestamp}.json"
                backup_path = os.path.join(BACKUP_DIR, backup_filename)
                with open(backup_path, 'w', encoding='utf-8') as bf:
                    json.dump(transactions, bf, ensure_ascii=False, indent=4)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "message": "Data berhasil disimpan ke database SQLite & dibackup."}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/settings":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()

                if "settings" in data and isinstance(data["settings"], dict):
                    for k, v in data["settings"].items():
                        cursor.execute('''
                            INSERT INTO settings (key, value) VALUES (?, ?)
                            ON CONFLICT(key) DO UPDATE SET value = ?
                        ''', (k, str(v) if v is not None else '', str(v) if v is not None else ''))
                else:
                    key = data.get('key')
                    value = data.get('value')
                    if not key:
                        conn.close()
                        raise Exception("Setting key is required")
                    cursor.execute('''
                        INSERT INTO settings (key, value) VALUES (?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = ?
                    ''', (key, str(value) if value is not None else '', str(value) if value is not None else ''))

                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "message": "Setting tersimpan permanen di server."}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/restore":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                filename = data.get('filename', '')

                if not filename:
                    raise Exception("Nama file backup tidak valid.")

                backup_path = os.path.join(BACKUP_DIR, filename)
                if not os.path.exists(backup_path):
                    raise Exception("File backup tidak ditemukan.")

                with open(backup_path, 'r', encoding='utf-8') as f:
                    backup_data = json.load(f)

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transactions")
                for t in backup_data:
                    cursor.execute('''
                        INSERT INTO transactions (tanggal, omset, spp, opp, jasa, hasil, catatan)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        t.get('tanggal', ''),
                        float(t.get('omset', 0) or 0),
                        float(t.get('spp', 0) or 0),
                        float(t.get('opp', 0) or 0),
                        float(t.get('jasa', 0) or 0),
                        float(t.get('hasil', 0) or 0),
                        str(t.get('catatan', '') or '')
                    ))
                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "message": f"Berhasil memulihkan database SQLite dari {filename}"}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/logo":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                import base64
                data = json.loads(post_data.decode('utf-8'))
                action = data.get('action', '')
                logo_path = os.path.join(DIRECTORY, "logo.ico")

                if action == 'reset':
                    if os.path.exists(logo_path):
                        os.remove(logo_path)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {
                        "success": True,
                        "has_custom_logo": False,
                        "logo_url": "/default_logo.ico",
                        "message": "Logo berhasil dikembalikan ke logo bawaan KasToko."
                    }
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return

                image_data = data.get('image', '')
                if not image_data:
                    raise Exception("Data gambar logo tidak boleh kosong.")
                
                if ',' in image_data:
                    header, encoded = image_data.split(',', 1)
                else:
                    encoded = image_data

                binary_data = base64.b64decode(encoded)
                with open(logo_path, 'wb') as f:
                    f.write(binary_data)

                mtime = int(os.path.getmtime(logo_path))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {
                    "success": True,
                    "has_custom_logo": True,
                    "logo_url": f"/logo.ico?t={mtime}",
                    "message": "Logo berhasil disimpan secara permanen di server."
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/services":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                srv_id = data.get('id')
                nama_pelanggan = str(data.get('nama_pelanggan', '')).strip()
                no_hp = str(data.get('no_hp', '')).strip()
                jenis_perangkat = str(data.get('jenis_perangkat', '')).strip()
                merk_model = str(data.get('merk_model', '')).strip()
                keluhan = str(data.get('keluhan', '')).strip()
                catatan_teknisi = str(data.get('catatan_teknisi', '')).strip()
                menu_servis = str(data.get('menu_servis', 'Diagnosa')).strip()
                status_servis = str(data.get('status_servis', 'Baru')).strip()
                estimasi_biaya = float(data.get('estimasi_biaya', 0) or 0)
                biaya_akhir = float(data.get('biaya_akhir', estimasi_biaya) or 0)
                status_pembayaran = str(data.get('status_pembayaran', 'Belum Bayar')).strip()
                sparepart_nama = str(data.get('sparepart_nama', '')).strip()
                sparepart_biaya = float(data.get('sparepart_biaya', 0) or 0)
                metode_pembayaran = str(data.get('metode_pembayaran', 'Tunai')).strip()
                tanggal_masuk = str(data.get('tanggal_masuk', datetime.date.today().strftime('%Y-%m-%d'))).strip()
                tanggal_selesai = str(data.get('tanggal_selesai', '')).strip()

                if not nama_pelanggan:
                    raise Exception("Nama pelanggan wajib diisi.")
                if not jenis_perangkat or not merk_model:
                    raise Exception("Jenis perangkat dan merk/model unit wajib diisi.")

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()

                # Simpan otomatis data pelanggan ke tabel customers
                cust_id = auto_save_customer(cursor, nama_pelanggan, no_hp)

                if srv_id:
                    cursor.execute('''
                        UPDATE services SET
                            customer_id = ?,
                            nama_pelanggan = ?,
                            no_hp = ?,
                            jenis_perangkat = ?,
                            merk_model = ?,
                            keluhan = ?,
                            catatan_teknisi = ?,
                            menu_servis = ?,
                            status_servis = ?,
                            estimasi_biaya = ?,
                            biaya_akhir = ?,
                            status_pembayaran = ?,
                            sparepart_nama = ?,
                            sparepart_biaya = ?,
                            metode_pembayaran = ?,
                            tanggal_masuk = ?,
                            tanggal_selesai = ?
                        WHERE id = ?
                    ''', (
                        cust_id, nama_pelanggan, no_hp, jenis_perangkat, merk_model,
                        keluhan, catatan_teknisi, menu_servis, status_servis,
                        estimasi_biaya, biaya_akhir, status_pembayaran,
                        sparepart_nama, sparepart_biaya, metode_pembayaran,
                        tanggal_masuk, tanggal_selesai, srv_id
                    ))
                    saved_id = srv_id
                    msg = "Data servis berhasil diperbarui."
                else:
                    kode_servis = generate_service_code(cursor)
                    cursor.execute('''
                        INSERT INTO services (
                            kode_servis, customer_id, nama_pelanggan, no_hp,
                            jenis_perangkat, merk_model, keluhan, catatan_teknisi,
                            menu_servis, status_servis, estimasi_biaya, biaya_akhir,
                            status_pembayaran, sparepart_nama, sparepart_biaya,
                            metode_pembayaran, tanggal_masuk, tanggal_selesai
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        kode_servis, cust_id, nama_pelanggan, no_hp,
                        jenis_perangkat, merk_model, keluhan, catatan_teknisi,
                        menu_servis, status_servis, estimasi_biaya, biaya_akhir,
                        status_pembayaran, sparepart_nama, sparepart_biaya,
                        metode_pembayaran, tanggal_masuk, tanggal_selesai
                    ))
                    saved_id = cursor.lastrowid
                    msg = f"Tiket servis baru #{kode_servis} berhasil disimpan."

                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "id": saved_id, "message": msg}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/services/status":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                srv_id = data.get('id')
                new_status = data.get('status_servis')
                biaya_akhir = data.get('biaya_akhir')
                status_pembayaran = data.get('status_pembayaran')
                sparepart_nama = data.get('sparepart_nama')
                sparepart_biaya = data.get('sparepart_biaya')
                metode_pembayaran = data.get('metode_pembayaran')
                catatan_teknisi = data.get('catatan_teknisi')

                if not srv_id or not new_status:
                    raise Exception("ID dan status servis diperlukan.")

                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                today_str = datetime.date.today().strftime('%Y-%m-%d')

                # Ambil data tiket saat ini
                cursor.execute("SELECT * FROM services WHERE id = ?", (srv_id,))
                srv_row = cursor.fetchone()
                if not srv_row:
                    conn.close()
                    raise Exception("Data servis tidak ditemukan.")

                updates = ["status_servis = ?"]
                params = [new_status]

                if new_status in ('Instan', 'Selesai', 'Diambil'):
                    updates.append("tanggal_selesai = CASE WHEN tanggal_selesai = '' OR tanggal_selesai IS NULL THEN ? ELSE tanggal_selesai END")
                    params.append(today_str)
                if biaya_akhir is not None:
                    updates.append("biaya_akhir = ?")
                    params.append(float(biaya_akhir or 0))
                if status_pembayaran:
                    updates.append("status_pembayaran = ?")
                    params.append(str(status_pembayaran))
                if sparepart_nama is not None:
                    updates.append("sparepart_nama = ?")
                    params.append(str(sparepart_nama).strip())
                if sparepart_biaya is not None:
                    updates.append("sparepart_biaya = ?")
                    params.append(float(sparepart_biaya or 0))
                if metode_pembayaran is not None:
                    updates.append("metode_pembayaran = ?")
                    params.append(str(metode_pembayaran).strip())
                if catatan_teknisi is not None:
                    updates.append("catatan_teknisi = ?")
                    params.append(str(catatan_teknisi).strip())

                params.append(srv_id)
                cursor.execute(f"UPDATE services SET {', '.join(updates)} WHERE id = ?", params)

                # Ambil data terbaru setelah update untuk sinkronisasi ke pembukuan
                cursor.execute("SELECT * FROM services WHERE id = ?", (srv_id,))
                updated_srv = cursor.fetchone()
                kode_servis = updated_srv["kode_servis"]
                nama_pelanggan = updated_srv["nama_pelanggan"]
                s_spp_biaya = float(updated_srv["sparepart_biaya"] or 0)
                s_spp_nama = str(updated_srv["sparepart_nama"] or "").strip()
                s_biaya_akhir = float(updated_srv["biaya_akhir"] or updated_srv["estimasi_biaya"] or 0)
                s_status_bayar = str(updated_srv["status_pembayaran"] or "Belum Bayar").strip()

                # Persentase jasa dari settings (default 20%)
                cursor.execute("SELECT value FROM settings WHERE key = 'inputPersenJasa'")
                persen_row = cursor.fetchone()
                persen_jasa = 20.0
                if persen_row and persen_row[0]:
                    try:
                        persen_jasa = float(persen_row[0])
                    except Exception:
                        persen_jasa = 20.0

                # Sinkronisasi ke tabel transactions (Pembukuan Toko) untuk Instan, Selesai, dan Diambil
                if new_status in ('Instan', 'Selesai', 'Diambil'):
                    if s_status_bayar == 'LUNAS':
                        omset_val = s_biaya_akhir
                        spp_val = s_spp_biaya
                        base_jasa = max(0.0, omset_val - spp_val)
                        jasa_val = round(base_jasa * (persen_jasa / 100.0))
                        hasil_val = round(omset_val - spp_val - jasa_val)
                        if new_status == 'Instan':
                            desc = f"Servis Instan Lunas #{kode_servis} - {nama_pelanggan}"
                        elif new_status == 'Diambil':
                            desc = f"Servis Lunas #{kode_servis} - {nama_pelanggan}"
                        else:
                            desc = f"Servis Selesai (Lunas) #{kode_servis} - {nama_pelanggan}"
                        if s_spp_nama:
                            desc += f" ({s_spp_nama})"

                        cursor.execute("SELECT id FROM transactions WHERE service_id = ?", (srv_id,))
                        trans_row = cursor.fetchone()
                        if trans_row:
                            cursor.execute('''
                                UPDATE transactions SET
                                    tanggal = ?,
                                    omset = ?,
                                    spp = ?,
                                    jasa = ?,
                                    hasil = ?,
                                    catatan = ?
                                WHERE service_id = ?
                            ''', (today_str, omset_val, spp_val, jasa_val, hasil_val, desc, srv_id))
                        else:
                            cursor.execute('''
                                INSERT INTO transactions (tanggal, omset, spp, opp, jasa, hasil, catatan, service_id)
                                VALUES (?, ?, ?, 0, ?, ?, ?, ?)
                            ''', (today_str, omset_val, spp_val, jasa_val, hasil_val, desc, srv_id))
                    else:
                        # Jika belum lunas, catat modal sparepart (SPP) jika ada
                        desc_prefix = "Servis Instan" if new_status == 'Instan' else ("Servis Diambil" if new_status == 'Diambil' else "SPP Servis")
                        desc = f"{desc_prefix} (Belum Lunas) #{kode_servis} - {nama_pelanggan}"
                        if s_spp_nama:
                            desc += f" ({s_spp_nama})"

                        cursor.execute("SELECT id FROM transactions WHERE service_id = ?", (srv_id,))
                        trans_row = cursor.fetchone()
                        if s_spp_biaya > 0:
                            if trans_row:
                                cursor.execute('''
                                    UPDATE transactions SET
                                        tanggal = ?,
                                        omset = 0,
                                        spp = ?,
                                        jasa = 0,
                                        hasil = -?,
                                        catatan = ?
                                    WHERE service_id = ?
                                ''', (today_str, s_spp_biaya, s_spp_biaya, desc, srv_id))
                            else:
                                cursor.execute('''
                                    INSERT INTO transactions (tanggal, omset, spp, opp, jasa, hasil, catatan, service_id)
                                    VALUES (?, 0, ?, 0, 0, ?, ?, ?)
                                ''', (today_str, s_spp_biaya, -s_spp_biaya, desc, srv_id))
                        elif trans_row:
                            cursor.execute("DELETE FROM transactions WHERE service_id = ?", (srv_id,))

                elif new_status in ('Baru', 'Batal'):
                    # Jika dibatalkan atau dikembalikan ke baru, hapus transaksi pembukuan terkait
                    cursor.execute("DELETE FROM transactions WHERE service_id = ?", (srv_id,))

                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "message": f"Status servis berhasil diubah ke '{new_status}'."}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/services/delete":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                srv_id = data.get('id')
                if not srv_id:
                    raise Exception("ID servis diperlukan.")

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM services WHERE id = ?", (srv_id,))
                cursor.execute("DELETE FROM transactions WHERE service_id = ?", (srv_id,))
                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "message": "Data servis berhasil dihapus."}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/services/clear":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
                role = str(data.get('role', '')).strip().lower()
                if role != 'superadmin':
                    raise Exception("Akses Ditolak: Hanya Superadmin yang berhak mereset data servis & nomor nota.")

                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Safety: Buat snapshot cadangan sebelum clear data
                if not os.path.exists(BACKUP_DIR):
                    os.makedirs(BACKUP_DIR, exist_ok=True)
                cursor.execute("SELECT * FROM services")
                s_rows = [dict(r) for r in cursor.fetchall()]
                cursor.execute("SELECT * FROM customers")
                c_rows = [dict(r) for r in cursor.fetchall()]
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                backup_path = os.path.join(BACKUP_DIR, f"backup_pre_clear_services_{timestamp}.json")
                with open(backup_path, 'w', encoding='utf-8') as bf:
                    json.dump({"services": s_rows, "customers": c_rows}, bf, ensure_ascii=False, indent=2)

                # Reset data servis, pelanggan, transaksi terkait servis, dan reset urutan nomor nota ke 001
                cursor.execute("DELETE FROM services")
                cursor.execute("DELETE FROM customers")
                cursor.execute("DELETE FROM transactions WHERE service_id IS NOT NULL")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('services', 'customers')")
                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "message": "Seluruh data servis & pelanggan berhasil di-reset! Nomor nota kembali ke 001."}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/customers":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                nama = data.get('nama', '').strip()
                no_hp = data.get('no_hp', '').strip()
                alamat = data.get('alamat', '').strip()
                if not nama:
                    raise Exception("Nama pelanggan wajib diisi.")

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cust_id = auto_save_customer(cursor, nama, no_hp, alamat)
                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "id": cust_id, "message": "Data pelanggan berhasil disimpan."}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/export":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                filename = data.get('filename', f"Laporan_{datetime.date.today()}.xls")
                html_content = data.get('html', '')

                if not os.path.exists(BACKUP_DIR):
                    os.makedirs(BACKUP_DIR, exist_ok=True)

                export_path = os.path.join(BACKUP_DIR, filename)
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "message": f"Tersimpan di backup/{filename}"}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif path == "/api/print/test":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
                p_name = data.get('printer_name') or (printer_service.get_default_printer() if printer_service else None)
                p_type = data.get('type', 'receipt')
                paper_w = str(data.get('paper_width', '58'))
                lbl_size = str(data.get('label_size', '40x30'))
                lbl_mode = str(data.get('mode', 'tspl'))
                density = str(data.get('density', 'high'))

                if not p_name:
                    raise Exception("Printer tidak ditemukan atau belum dipilih.")

                if p_type == 'label':
                    raw_bytes = printer_service.format_label_test_page(p_name, label_size=lbl_size, mode=lbl_mode)
                    doc_title = "KasToko Test Label"
                else:
                    raw_bytes = printer_service.format_receipt_test_page(p_name, paper_width=paper_w, density=density)
                    doc_title = "KasToko Test Receipt"

                printer_service.send_raw_to_printer(p_name, raw_bytes, doc_name=doc_title)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": f"Uji cetak berhasil dikirim langsung ke '{p_name}'!"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        elif path == "/api/print/receipt":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
                settings = get_store_settings_dict()
                srv_id = data.get('service_id')
                srv_obj = data.get('service')
                p_name = data.get('printer_name') or settings.get('nota_printer_name') or (printer_service.get_default_printer() if printer_service else None)
                paper_w = str(data.get('paper_width') or settings.get('nota_paper_size') or '58')
                density = str(data.get('density') or settings.get('print_density') or 'high')
                receipt_type = str(data.get('receipt_type') or 'terima')
                is_ambil = (receipt_type == 'ambil')

                if not p_name:
                    raise Exception("Printer Nota belum dipilih. Silakan atur printer di menu Pengaturan.")

                if not srv_obj and srv_id:
                    conn = sqlite3.connect(DB_FILE)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM services WHERE id = ?", (srv_id,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        srv_obj = dict(row)

                if not srv_obj:
                    raise Exception("Data servis tidak ditemukan untuk dicetak.")

                store_prof = data.get('store_profile') or {
                    "name": settings.get('store_name', 'AUTOCASH SERVIS'),
                    "address": settings.get('store_address', ''),
                    "phone": settings.get('store_phone', '')
                }

                raw_bytes = printer_service.format_escpos_receipt(srv_obj, store_profile=store_prof, paper_width=paper_w, density=density, is_ambil=is_ambil)
                doc_title = f"Nota {srv_obj.get('kode_servis', '')}"
                printer_service.send_raw_to_printer(p_name, raw_bytes, doc_name=doc_title)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": f"Nota berhasil dicetak langsung ke printer '{p_name}'!"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        elif path == "/api/print/label":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
                settings = get_store_settings_dict()
                srv_id = data.get('service_id')
                srv_obj = data.get('service')
                p_name = data.get('printer_name') or settings.get('label_printer_name') or (printer_service.get_default_printer() if printer_service else None)
                lbl_size = str(data.get('label_size') or settings.get('label_paper_size') or '40x30')
                lbl_mode = str(data.get('mode') or settings.get('label_mode') or 'tspl')

                if not p_name:
                    raise Exception("Printer Label belum dipilih. Silakan atur printer di menu Pengaturan.")

                if not srv_obj and srv_id:
                    conn = sqlite3.connect(DB_FILE)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM services WHERE id = ?", (srv_id,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        srv_obj = dict(row)

                if not srv_obj:
                    raise Exception("Data tiket servis tidak ditemukan untuk dicetak.")

                store_prof = data.get('store_profile') or {
                    "name": settings.get('store_name', 'AUTOCASH SERVIS')
                }

                if lbl_mode == 'escpos':
                    raw_bytes = printer_service.format_escpos_label(srv_obj, label_size=lbl_size, store_profile=store_prof)
                else:
                    raw_bytes = printer_service.format_tspl_label(srv_obj, label_size=lbl_size, store_profile=store_prof)

                doc_title = f"Label {srv_obj.get('kode_servis', '')}"
                printer_service.send_raw_to_printer(p_name, raw_bytes, doc_name=doc_title)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": f"Label stiker berhasil dicetak langsung ke '{p_name}'!"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        elif path == "/api/print/both":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
                settings = get_store_settings_dict()
                srv_id = data.get('service_id')
                srv_obj = data.get('service')

                nota_p = data.get('receipt_printer') or settings.get('nota_printer_name') or (printer_service.get_default_printer() if printer_service else None)
                label_p = data.get('label_printer') or settings.get('label_printer_name') or (printer_service.get_default_printer() if printer_service else None)
                paper_w = str(data.get('paper_width') or settings.get('nota_paper_size') or '58')
                density = str(data.get('density') or settings.get('print_density') or 'high')
                receipt_type = str(data.get('receipt_type') or 'terima')
                is_ambil = (receipt_type == 'ambil')
                lbl_size = str(data.get('label_size') or settings.get('label_paper_size') or '40x30')
                lbl_mode = str(data.get('label_mode') or settings.get('label_mode') or 'tspl')
                delay_ms = int(data.get('delay_ms') or settings.get('print_delay_ms') or 600)

                if not nota_p or not label_p:
                    raise Exception("Printer Nota atau Printer Label belum dikonfigurasi.")

                if not srv_obj and srv_id:
                    conn = sqlite3.connect(DB_FILE)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM services WHERE id = ?", (srv_id,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        srv_obj = dict(row)

                if not srv_obj:
                    raise Exception("Data servis tidak ditemukan.")

                store_prof = data.get('store_profile') or {
                    "name": settings.get('store_name', 'AUTOCASH SERVIS'),
                    "address": settings.get('store_address', ''),
                    "phone": settings.get('store_phone', '')
                }

                # 1. Cetak Nota ke Printer 1
                receipt_bytes = printer_service.format_escpos_receipt(srv_obj, store_profile=store_prof, paper_width=paper_w, density=density, is_ambil=is_ambil)
                printer_service.send_raw_to_printer(nota_p, receipt_bytes, doc_name=f"Nota {srv_obj.get('kode_servis', '')}")

                # Jeda waktu (delay)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)

                # 2. Cetak Label ke Printer 2
                if lbl_mode == 'escpos':
                    label_bytes = printer_service.format_escpos_label(srv_obj, label_size=lbl_size, store_profile=store_prof)
                else:
                    label_bytes = printer_service.format_tspl_label(srv_obj, label_size=lbl_size, store_profile=store_prof)

                printer_service.send_raw_to_printer(label_p, label_bytes, doc_name=f"Label {srv_obj.get('kode_servis', '')}")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": f"Nota tercetak di '{nota_p}', Label tercetak di '{label_p}' bergiliran!"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode('utf-8'))

        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        print(f"==============================================================")
        print(f"  KasToko - Server Pembukuan Toko")
        print(f"  Port: {PORT}")
        print(f"  URL : http://localhost:{PORT}")
        print(f"  Database : {DB_FILE}")
        print(f"==============================================================")
        print(f"[INFO] Server aktif. Minimize jendela ini untuk berjalan di background.")
        print(f"[INFO] Klik kanan icon Tray untuk 'Open' atau 'Quit'.\n")

        # Inisialisasi System Tray & Minimize-to-Tray Manager
        tray = None
        try:
            from tray_manager import init_tray_manager
            def on_server_quit():
                threading.Thread(target=httpd.shutdown, daemon=True).start()
            tray = init_tray_manager(PORT, on_quit=on_server_quit)
        except Exception as e:
            print(f"[WARN] Tray manager tidak dapat diaktifkan: {e}")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[INFO] Menghentikan server...")
        finally:
            if tray:
                tray.stop()
