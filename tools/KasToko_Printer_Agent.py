# -*- coding: utf-8 -*-
"""
tools/KasToko_Printer_Agent.py - Tool Agen Pendeteksi & Pencetak Hardware Printer KasToko
---------------------------------------------------------------------------------------
Jalankan tool ini di komputer / laptop kasir mana pun yang membuka aplikasi KasToko.
Tool ini secara otomatis:
1. Mendeteksi seluruh printer thermal (USB / Bluetooth / Jaringan) yang terpasang di PC ini.
2. Membuka server mini lokal (port 18080) dengan dukungan Private Network Access (PNA CORS)
   sehingga web browser di https://autocash.dhanzcell.my.id langsung mengenali printer di PC ini.
3. Menghubungkan printer di PC ini ke server pusat KasToko via Cloud Relay Tunnel.
4. Menerima dan mengeksekusi cetak nota kasir & label barcode secara instan tanpa dialog Windows.
"""

import sys
import os
import time
import json
import socket
import platform
import base64
import urllib.request
import urllib.error
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Konfigurasi Port Agen Lokal & Server Pusat
AGENT_PORT = 18080
DEFAULT_CENTRAL_SERVER = "https://autocash.dhanzcell.my.id"

# Inisialisasi Win32 Spooler API
winspool = None
if os.name == "nt":
    try:
        import ctypes
        from ctypes import wintypes
        winspool = ctypes.WinDLL("winspool.drv")

        class DOC_INFO_1W(ctypes.Structure):
            _fields_ = [
                ("pDocName", wintypes.LPWSTR),
                ("pOutputFile", wintypes.LPWSTR),
                ("pDatatype", wintypes.LPWSTR)
            ]

        class PRINTER_INFO_2W(ctypes.Structure):
            _fields_ = [
                ("pServerName", wintypes.LPWSTR),
                ("pPrinterName", wintypes.LPWSTR),
                ("pShareName", wintypes.LPWSTR),
                ("pPortName", wintypes.LPWSTR),
                ("pDriverName", wintypes.LPWSTR),
                ("pComment", wintypes.LPWSTR),
                ("pLocation", wintypes.LPWSTR),
                ("pDevMode", ctypes.c_void_p),
                ("pSepFile", wintypes.LPWSTR),
                ("pPrintProcessor", wintypes.LPWSTR),
                ("pDatatype", wintypes.LPWSTR),
                ("pParameters", wintypes.LPWSTR),
                ("pSecurityDescriptor", ctypes.c_void_p),
                ("Attributes", wintypes.DWORD),
                ("Priority", wintypes.DWORD),
                ("DefaultPriority", wintypes.DWORD),
                ("StartTime", wintypes.DWORD),
                ("UntilTime", wintypes.DWORD),
                ("Status", wintypes.DWORD),
                ("cJobs", wintypes.DWORD),
                ("AveragePPM", wintypes.DWORD),
            ]
    except Exception as e:
        print(f"[WARN] Gagal inisialisasi winspool: {e}")
        winspool = None

# PIL Image untuk pengolahan gambar nota
try:
    from PIL import Image
except ImportError:
    Image = None

def get_device_id():
    """Mengambil / membuat ID unik perangkat ini yang persisten."""
    config_dir = os.path.join(os.path.expanduser("~"), ".kastoko_agent")
    os.makedirs(config_dir, exist_ok=True)
    id_file = os.path.join(config_dir, "device_id.txt")
    if os.path.exists(id_file):
        try:
            with open(id_file, "r", encoding="utf-8") as f:
                did = f.read().strip()
                if did:
                    return did
        except Exception:
            pass

    import uuid
    new_id = f"dev_{uuid.uuid4().hex[:12]}"
    try:
        with open(id_file, "w", encoding="utf-8") as f:
            f.write(new_id)
    except Exception:
        pass
    return new_id

DEVICE_ID = get_device_id()
MACHINE_NAME = platform.node() or "PC-Klien"

def get_installed_printers():
    """Mengambil daftar seluruh printer yang terhubung di PC ini."""
    printers = []
    if os.name == "nt" and winspool:
        try:
            flags = 0x00000002 | 0x00000004
            needed = wintypes.DWORD(0)
            returned = wintypes.DWORD(0)
            winspool.EnumPrintersW(flags, None, 2, None, 0, ctypes.byref(needed), ctypes.byref(returned))
            if needed.value > 0:
                buf = (ctypes.c_byte * needed.value)()
                if winspool.EnumPrintersW(flags, None, 2, buf, needed.value, ctypes.byref(needed), ctypes.byref(returned)):
                    ptr = ctypes.cast(buf, ctypes.POINTER(PRINTER_INFO_2W))
                    for i in range(returned.value):
                        printers.append({
                            "name": ptr[i].pPrinterName,
                            "port": ptr[i].pPortName,
                            "driver": ptr[i].pDriverName,
                            "is_default": False
                        })
        except Exception as e:
            print(f"[AGENT] Error enum printers winspool: {e}")

    # Fallback jika winspool gagal: gunakan PowerShell Get-Printer
    if not printers and os.name == "nt":
        try:
            import subprocess
            cmd = "Get-Printer | Select-Object Name, PortName, DriverName, Type | ConvertTo-Json"
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=3)
            if proc.returncode == 0 and proc.stdout.strip():
                p_data = json.loads(proc.stdout)
                if isinstance(p_data, dict):
                    p_data = [p_data]
                for item in p_data:
                    printers.append({
                        "name": item.get("Name"),
                        "port": item.get("PortName", "USB"),
                        "driver": item.get("DriverName", ""),
                        "is_default": False
                    })
        except Exception as e:
            print(f"[AGENT] Error PowerShell Get-Printer: {e}")

    # Tandai default printer
    def_name = get_default_printer()
    for p in printers:
        if def_name and p["name"].lower() == def_name.lower():
            p["is_default"] = True

    return printers

def get_default_printer():
    """Mengambil default printer Windows."""
    if os.name == "nt" and winspool:
        try:
            size = wintypes.DWORD(0)
            winspool.GetDefaultPrinterW(None, ctypes.byref(size))
            if size.value > 0:
                buf = ctypes.create_unicode_buffer(size.value)
                if winspool.GetDefaultPrinterW(buf, ctypes.byref(size)):
                    return buf.value
        except Exception:
            pass
    return None

def send_raw_to_printer(printer_name: str, data: bytes, doc_name: str = "KasToko Print Job"):
    """Mengirim byte raw langsung ke Windows Spooler tanpa dialog."""
    if not winspool:
        raise RuntimeError("Windows Print Spooler (winspool.drv) tidak tersedia.")
    if not printer_name:
        raise ValueError("Nama printer belum ditentukan.")

    hPrinter = wintypes.HANDLE()
    if not winspool.OpenPrinterW(printer_name, ctypes.byref(hPrinter), None):
        err = ctypes.GetLastError()
        raise RuntimeError(f"Gagal membuka printer '{printer_name}' (Windows Error {err}).")

    try:
        doc_info = DOC_INFO_1W()
        doc_info.pDocName = doc_name
        doc_info.pOutputFile = None
        doc_info.pDatatype = "RAW"

        job_id = winspool.StartDocPrinterW(hPrinter, 1, ctypes.byref(doc_info))
        if job_id <= 0:
            err = ctypes.GetLastError()
            raise RuntimeError(f"Gagal memulai print job (Windows Error {err}).")

        try:
            if not winspool.StartPagePrinter(hPrinter):
                err = ctypes.GetLastError()
                raise RuntimeError(f"Gagal memulai halaman print (Windows Error {err}).")

            written = wintypes.DWORD(0)
            data_len = len(data)
            success = winspool.WritePrinter(hPrinter, data, data_len, ctypes.byref(written))
            if not success or written.value != data_len:
                err = ctypes.GetLastError()
                raise RuntimeError(f"Gagal mengirim data ke printer (tertulis {written.value}/{data_len}, Error {err}).")

            winspool.EndPagePrinter(hPrinter)
        finally:
            winspool.EndDocPrinter(hPrinter)
    finally:
        winspool.ClosePrinter(hPrinter)
    return True

def convert_image_to_tspl_or_escpos(image_data: str, is_tspl: bool = True):
    """Konversi gambar base64 ke format raw byte TSPL atau ESC/POS."""
    if not Image:
        raise RuntimeError("Modul Pillow (PIL) belum terpasang. Jalankan: pip install pillow")

    import io
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    img_bytes = base64.b64decode(image_data)
    img = Image.open(io.BytesIO(img_bytes)).convert("L")

    # Target thermal 78mm = 576 px, 58mm = 384 px
    target_width = 576 if is_tspl else 384
    w_orig, h_orig = img.size
    target_height = int((target_width / float(w_orig)) * h_orig)
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    # Thresholding monochrome
    threshold = 175
    img = img.point(lambda p: 255 if p > threshold else 0, mode='1')

    width, height = img.size
    bytes_per_row = (width + 7) // 8
    img_data = img.tobytes()

    if is_tspl:
        # TSPL BITMAP 0,0,width_bytes,height,0,...
        # Invert agar 1 = dot hitam
        inverted = bytearray(len(img_data))
        for i in range(len(img_data)):
            inverted[i] = ~img_data[i] & 0xFF

        h_mm = max(20, int(round(height / 8.0)))
        w_mm = int(round(width / 8.0))
        header = (
            f"SIZE {w_mm} mm,{h_mm} mm\n"
            f"GAP 0 mm,0 mm\n"
            f"DIRECTION 1\n"
            f"REFERENCE 0,0\n"
            f"CLS\n"
            f"BITMAP 0,0,{bytes_per_row},{height},0,"
        ).encode('latin1')
        footer = b"\nPRINT 1,1\n"
        return header + bytes(inverted) + footer
    else:
        # ESC/POS GS v 0
        inverted = bytearray(len(img_data))
        for i in range(len(img_data)):
            inverted[i] = ~img_data[i] & 0xFF

        xL = bytes_per_row & 0xFF
        xH = (bytes_per_row >> 8) & 0xFF
        yL = height & 0xFF
        yH = (height >> 8) & 0xFF

        init_cmd = b"\x1B\x40"
        bit_cmd = b"\x1D\x76\x30\x00" + bytes([xL, xH, yL, yH]) + bytes(inverted)
        feed_cmd = b"\x1B\x64\x03\x1D\x56\x00"
        return init_cmd + bit_cmd + feed_cmd

class KasTokoAgentHTTPHandler(BaseHTTPRequestHandler):
    """HTTP Handler dengan dukungan penuh Private Network Access (PNA) CORS."""

    def log_message(self, format, *args):
        # Ringkas log agar terminal tetap bersih
        pass

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Cache-Control")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/status" or path == "/":
            printers = get_installed_printers()
            def_p = get_default_printer()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.end_headers()
            resp = {
                "success": True,
                "app": "KasToko Local Print Agent",
                "device_id": DEVICE_ID,
                "machine_name": MACHINE_NAME,
                "printer_count": len(printers),
                "default_printer": def_p
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))

        elif path == "/api/printers":
            printers = get_installed_printers()
            def_p = get_default_printer()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._set_cors_headers()
            self.end_headers()
            resp = {
                "success": True,
                "source": "local_agent",
                "device_id": DEVICE_ID,
                "machine_name": MACHINE_NAME,
                "printers": printers,
                "default": def_p
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length) if length > 0 else b"{}"

        try:
            data = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            data = {}

        if path == "/api/print/receipt" or path == "/api/print/both":
            try:
                printer_name = data.get("printer_name") or data.get("receipt_printer") or get_default_printer()
                if not printer_name:
                    raise Exception("Printer belum ditentukan.")

                image_data = data.get("image_data")
                paper_w = str(data.get("paper_width", "78"))
                is_tspl = ("78" in paper_w or "label" in str(printer_name).lower() or data.get("mode") == "tspl")

                if image_data and Image:
                    raw_bytes = convert_image_to_tspl_or_escpos(image_data, is_tspl=is_tspl)
                else:
                    # Fallback test teks
                    raw_bytes = (
                        b"\x1B\x40\x1B\x61\x01\x1B\x45\x01KASTOKO POS PRINT\x1B\x45\x00\n"
                        b"Cetak Langsung via Local Agent\n"
                        b"--------------------------------\n\n\n\x1D\x56\x00"
                    )

                send_raw_to_printer(printer_name, raw_bytes, doc_name="KasToko Nota Receipt")
                print(f"[AGENT] Sukses cetak nota ke '{printer_name}' di PC {MACHINE_NAME}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": f"Nota berhasil dicetak langsung ke printer '{printer_name}' di PC ini!"
                }).encode("utf-8"))
            except Exception as e:
                print(f"[AGENT] Gagal cetak nota: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))

        elif path == "/api/print/test":
            try:
                p_name = data.get("printer_name") or get_default_printer()
                p_type = data.get("type", "receipt")
                if not p_name:
                    raise Exception("Printer belum dipilih.")

                if p_type == "label" or "label" in str(p_name).lower():
                    # TSPL Test Label
                    tspl_cmd = (
                        "SIZE 40 mm,30 mm\n"
                        "GAP 2 mm,0 mm\n"
                        "DIRECTION 1\n"
                        "REFERENCE 0,0\n"
                        "CLS\n"
                        "TEXT 20,20,\"3\",0,1,1,\"KASTOKO AGENT\"\n"
                        f"TEXT 20,60,\"2\",0,1,1,\"{MACHINE_NAME}\"\n"
                        "TEXT 20,95,\"2\",0,1,1,\"Status: TERHUBUNG\"\n"
                        "BARCODE 20,130,\"128\",40,1,0,2,2,\"TEST-OK\"\n"
                        "PRINT 1,1\n"
                    ).encode('latin1')
                    send_raw_to_printer(p_name, tspl_cmd, doc_name="Test Stiker Label")
                else:
                    # ESC/POS Test Receipt
                    esc_text = (
                        "\x1B\x40"
                        "\x1B\x61\x01"
                        "\x1B\x45\x01KASTOKO PRINT AGENT\x1B\x45\x00\n"
                        "================================\n"
                        "UJI KONEKSI PRINTER LOKAL\n"
                        f"PC Klien : {MACHINE_NAME}\n"
                        f"Perangkat: {p_name}\n"
                        f"Waktu    : {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        "Status   : BERHASIL TERHUBUNG!\n"
                        "================================\n\n\n\n"
                    )
                    esc_cmd = esc_text.encode('latin1', errors='replace') + b"\x1D\x56\x00"
                    send_raw_to_printer(p_name, esc_cmd, doc_name="Test Cetak Thermal")

                print(f"[AGENT] Uji cetak sukses ke '{p_name}'")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "message": f"Uji cetak berhasil terkirim ke printer '{p_name}' di PC ini!"
                }).encode("utf-8"))
            except Exception as e:
                print(f"[AGENT] Gagal uji cetak: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "message": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self._set_cors_headers()
            self.end_headers()

def heartbeat_registration_loop(server_url):
    """Background worker untuk mendaftarkan printer lokal ini ke server pusat secara berkala."""
    time.sleep(1.0)
    while True:
        try:
            printers = get_installed_printers()
            def_p = get_default_printer()
            payload = {
                "device_id": DEVICE_ID,
                "machine_name": MACHINE_NAME,
                "agent_port": AGENT_PORT,
                "printers": printers,
                "default": def_p
            }
            req_data = json.dumps(payload).encode("utf-8")
            reg_url = f"{server_url}/api/printer-agent/register"

            req = urllib.request.Request(
                reg_url,
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": f"KasTokoPrinterAgent/1.0 ({MACHINE_NAME})"
                }
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                pass
        except Exception:
            pass
        time.sleep(12)

def start_agent_server(central_server=DEFAULT_CENTRAL_SERVER):
    # Banner terminal
    print("=" * 64)
    print("          KASTOKO - LOCAL HARDWARE PRINT AGENT")
    print("=" * 64)
    print(f"Nama Komputer  : {MACHINE_NAME}")
    print(f"Device ID      : {DEVICE_ID}")
    print(f"Port Lokal     : http://127.0.0.1:{AGENT_PORT}")
    print(f"Server Pusat   : {central_server}")
    print("-" * 64)

    printers = get_installed_printers()
    def_p = get_default_printer()
    print(f"Printer Terdeteksi di PC ini ({len(printers)} printer):")
    if not printers:
        print("  [!] Belum ada printer yang terdeteksi di Windows.")
        print("      Pastikan kabel USB printer thermal menyala & driver terinstall.")
    else:
        for idx, p in enumerate(printers, 1):
            def_mark = " (Default)" if p.get("is_default") else ""
            print(f"  [{idx}] {p['name']} [{p.get('port', 'USB')}]{def_mark}")

    print("-" * 64)
    print("Tool ini mendengarkan koneksi dari web KasToko.")
    print("JANGAN TUTUP jendela ini selama kasir beroperasi!")
    print("=" * 64 + "\n")

    # Jalankan background thread heartbeat
    hb_thread = threading.Thread(target=heartbeat_registration_loop, args=(central_server,), daemon=True)
    hb_thread.start()

    # Jalankan HTTP Server
    try:
        server = HTTPServer(("0.0.0.0", AGENT_PORT), KasTokoAgentHTTPHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Agen printer dihentikan oleh pengguna.")
    except Exception as e:
        print(f"\n[ERROR] Gagal menjalankan agen printer pada port {AGENT_PORT}: {e}")

if __name__ == "__main__":
    srv_target = DEFAULT_CENTRAL_SERVER
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        srv_target = sys.argv[1].rstrip("/")
    start_agent_server(srv_target)
