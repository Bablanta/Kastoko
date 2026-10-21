import http.server
import socketserver
import os
import json
import sqlite3
import datetime
import urllib.parse

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

init_db()

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == "/api/transactions":
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

        elif self.path == "/api/settings":
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

        elif self.path == "/api/backups":
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
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/transactions":
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

        elif self.path == "/api/settings":
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

        elif self.path == "/api/restore":
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

        elif self.path == "/api/logo":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                import base64
                data = json.loads(post_data.decode('utf-8'))
                image_data = data.get('image', '')
                
                if ',' in image_data:
                    header, encoded = image_data.split(',', 1)
                else:
                    encoded = image_data

                binary_data = base64.b64decode(encoded)
                logo_path = os.path.join(DIRECTORY, "logo.ico")
                
                with open(logo_path, 'wb') as f:
                    f.write(binary_data)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": True, "message": "Logo berhasil disimpan secara permanen di server."}
                self.wfile.write(json.dumps(response).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"success": False, "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))

        elif self.path == "/api/export":
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
        print(f"Server Pembukuan Toko berjalan di http://localhost:{PORT}")
        print(f"Database SQLite terpusat di: {DB_FILE}")
        print(f"Folder Backup JSON: {BACKUP_DIR}")
        httpd.serve_forever()
