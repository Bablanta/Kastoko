import http.server
import socketserver
import os
import json
import sqlite3
import datetime
import urllib.parse
import threading
import signal

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

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/transactions":
            try:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT id, tanggal, omset, spp, opp, jasa, hasil, catatan FROM transactions ORDER BY id ASC")
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
                        "catatan": row["catatan"] or ""
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
                key = data.get('key')
                value = data.get('value')

                if not key:
                    raise Exception("Setting key is required")

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
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
                            tanggal_masuk = ?,
                            tanggal_selesai = ?
                        WHERE id = ?
                    ''', (
                        cust_id, nama_pelanggan, no_hp, jenis_perangkat, merk_model,
                        keluhan, catatan_teknisi, menu_servis, status_servis,
                        estimasi_biaya, biaya_akhir, status_pembayaran,
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
                            status_pembayaran, tanggal_masuk, tanggal_selesai
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        kode_servis, cust_id, nama_pelanggan, no_hp,
                        jenis_perangkat, merk_model, keluhan, catatan_teknisi,
                        menu_servis, status_servis, estimasi_biaya, biaya_akhir,
                        status_pembayaran, tanggal_masuk, tanggal_selesai
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
                if not srv_id or not new_status:
                    raise Exception("ID dan status servis diperlukan.")

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                if new_status in ('Selesai', 'Diambil'):
                    today_str = datetime.date.today().strftime('%Y-%m-%d')
                    cursor.execute("UPDATE services SET status_servis = ?, tanggal_selesai = CASE WHEN tanggal_selesai = '' OR tanggal_selesai IS NULL THEN ? ELSE tanggal_selesai END WHERE id = ?", (new_status, today_str, srv_id))
                else:
                    cursor.execute("UPDATE services SET status_servis = ? WHERE id = ?", (new_status, srv_id))
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
