# -*- coding: utf-8 -*-
"""
printer_service.py - Module Direct Raw Printing via Windows Spooler API (winspool.drv)
0% .NET Framework dependency - Native Win32 C ABI via CPython ctypes.
"""

import ctypes
from ctypes import wintypes
import datetime

# Load Windows Spooler library
try:
    winspool = ctypes.WinDLL("winspool.drv")
except Exception as e:
    winspool = None
    print(f"[WARN] winspool.drv tidak dapat dimuat: {e}")

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

def get_installed_printers():
    """Mengambil daftar seluruh printer yang terpasang di Windows (Lokal & Network)."""
    if not winspool:
        return []

    flags = 0x00000002 | 0x00000004  # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    needed = wintypes.DWORD(0)
    returned = wintypes.DWORD(0)

    winspool.EnumPrintersW(flags, None, 2, None, 0, ctypes.byref(needed), ctypes.byref(returned))
    if needed.value == 0:
        return []

    buf = (ctypes.c_byte * needed.value)()
    success = winspool.EnumPrintersW(flags, None, 2, buf, needed.value, ctypes.byref(needed), ctypes.byref(returned))
    if not success:
        return []

    ptr = ctypes.cast(buf, ctypes.POINTER(PRINTER_INFO_2W))
    printers = []
    for i in range(returned.value):
        printers.append({
            "name": ptr[i].pPrinterName,
            "port": ptr[i].pPortName,
            "driver": ptr[i].pDriverName,
            "is_default": False
        })

    def_name = get_default_printer()
    for p in printers:
        if def_name and p["name"] == def_name:
            p["is_default"] = True

    return printers

def get_default_printer():
    """Mengambil nama printer default Windows."""
    if not winspool:
        return None
    size = wintypes.DWORD(0)
    winspool.GetDefaultPrinterW(None, ctypes.byref(size))
    if size.value == 0:
        return None
    buf = ctypes.create_unicode_buffer(size.value)
    if winspool.GetDefaultPrinterW(buf, ctypes.byref(size)):
        return buf.value
    return None

def send_raw_to_printer(printer_name: str, data: bytes, doc_name: str = "KasToko Raw Print") -> bool:
    """
    Mengirim byte raw (ESC/POS atau TSPL) langsung ke Windows Print Spooler (RAW datatype).
    Melewati seluruh dialog UI Windows, langsung ditembak ke hardware thermal printer!
    """
    if not winspool:
        raise RuntimeError("Windows Spooler (winspool.drv) tidak tersedia.")

    if not printer_name:
        raise ValueError("Nama printer belum dipilih.")

    hPrinter = wintypes.HANDLE()
    if not winspool.OpenPrinterW(printer_name, ctypes.byref(hPrinter), None):
        err = ctypes.GetLastError()
        raise RuntimeError(f"Gagal membuka printer '{printer_name}' (Error {err}). Pastikan printer terhubung dan nama sesuai.")

    try:
        doc_info = DOC_INFO_1W()
        doc_info.pDocName = doc_name
        doc_info.pOutputFile = None
        doc_info.pDatatype = "RAW"

        job_id = winspool.StartDocPrinterW(hPrinter, 1, ctypes.byref(doc_info))
        if job_id <= 0:
            err = ctypes.GetLastError()
            raise RuntimeError(f"Gagal memulai dokumen print (Error {err}).")

        try:
            if not winspool.StartPagePrinter(hPrinter):
                err = ctypes.GetLastError()
                raise RuntimeError(f"Gagal memulai halaman print (Error {err}).")

            written = wintypes.DWORD(0)
            data_len = len(data)
            success = winspool.WritePrinter(hPrinter, data, data_len, ctypes.byref(written))
            if not success or written.value != data_len:
                err = ctypes.GetLastError()
                raise RuntimeError(f"Gagal menulis data ke printer (tertulis {written.value}/{data_len}, Error {err}).")

            winspool.EndPagePrinter(hPrinter)
        finally:
            winspool.EndDocPrinter(hPrinter)
    finally:
        winspool.ClosePrinter(hPrinter)

    return True

# ========================================================
# ESC/POS FORMATTER UNTUK NOTA TRANSAKSI / TIKET SERVIS
# ========================================================

def format_escpos_receipt(service_dict: dict, store_profile: dict = None, paper_width: str = "58", density: str = "high", is_ambil: bool = False) -> bytes:
    """
    Menghasilkan byte stream ESC/POS murni untuk nota kasir thermal 58mm atau 80mm.
    Fitur:
    - Lebar kolom dinamis (58mm = 32 karakter, 80mm = 48 karakter).
    - Heating Density Maksimal (Double-strike / Emphasize) agar hasil cetak tebal, pekat & timbul.
    - Format rata tengah untuk header toko & footer ucapan, rata kiri untuk detail unit, dan rata kanan untuk nominal.
    """
    s = service_dict or {}
    prof = store_profile or {}

    col_width = 48 if str(paper_width) == "80" else 32
    div_line = ("-" * col_width) + "\n"
    dbl_line = ("=" * col_width) + "\n"

    # ESC/POS Control Codes
    ESC = b"\x1B"
    GS = b"\x1D"

    INIT = ESC + b"\x40"                    # Reset printer
    ALIGN_LEFT = ESC + b"\x61\x00"          # Rata kiri
    ALIGN_CENTER = ESC + b"\x61\x01"        # Rata tengah
    ALIGN_RIGHT = ESC + b"\x61\x02"         # Rata kanan
    BOLD_ON = ESC + b"\x45\x01"             # Bold ON
    BOLD_OFF = ESC + b"\x45\x00"            # Bold OFF
    DOUBLE_STRIKE_ON = ESC + b"\x47\x01"    # Double-strike (pemanasan ganda agar tulisan timbul & pekat)
    DOUBLE_STRIKE_OFF = ESC + b"\x47\x00"
    DOUBLE_HEIGHT = GS + b"\x21\x01"        # Double height font
    NORMAL_SIZE = GS + b"\x21\x00"          # Normal font
    CUT_PAPER = GS + b"\x56\x41\x03"        # Cut paper (feed 3 baris lalu potong)

    buf = bytearray()
    buf.extend(INIT)

    # Tingkatkan ketebalan & kepekatan panas thermal jika density high
    if density in ("high", "max"):
        buf.extend(DOUBLE_STRIKE_ON)
        # ESC 7 (Set print heating parameter): heating dots, heating time, heating interval
        buf.extend(ESC + b"\x37\x07\xFE\x02")

    # Header Toko
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON)
    buf.extend(DOUBLE_HEIGHT)
    st_name = (prof.get("name") or "AUTOCASH SERVIS").strip()
    buf.extend((st_name + "\n").encode("cp437", errors="replace"))

    buf.extend(NORMAL_SIZE)
    buf.extend(BOLD_OFF)
    st_addr = (prof.get("address") or "").strip()
    if st_addr:
        buf.extend((st_addr + "\n").encode("cp437", errors="replace"))
    st_phone = (prof.get("phone") or "").strip()
    if st_phone:
        buf.extend((f"Telp/WA: {st_phone}\n").encode("cp437", errors="replace"))

    # Judul Nota
    buf.extend(BOLD_ON)
    if is_ambil:
        buf.extend(b"NOTA PENGAMBILAN & KWITANSI\n")
        tgl_str = s.get("tanggal_selesai") or datetime.date.today().strftime("%Y-%m-%d")
        buf.extend(BOLD_OFF)
        buf.extend((f"Tgl Keluar: {tgl_str}\n").encode("cp437", errors="replace"))
    else:
        buf.extend(b"TANDA TERIMA PENERIMAAN UNIT\n")
        tgl_str = s.get("tanggal_masuk") or datetime.date.today().strftime("%Y-%m-%d")
        buf.extend(BOLD_OFF)
        buf.extend((f"Tanggal: {tgl_str}\n").encode("cp437", errors="replace"))

    buf.extend(dbl_line.encode("cp437"))

    # Detail Pelanggan & Tiket
    buf.extend(ALIGN_LEFT)
    kode = str(s.get("kode_servis") or f"#{s.get('id', '')}").strip()
    nama_cust = str(s.get("nama_pelanggan") or "-").strip()
    no_hp = str(s.get("no_hp") or "-").strip()
    perangkat = str(s.get("jenis_perangkat") or "-").strip()
    unit = str(s.get("merk_model") or "-").strip()
    layanan = str(s.get("menu_servis") or "-").strip()
    keluhan = str(s.get("keluhan") or "-").strip()
    catatan_tek = str(s.get("catatan_teknisi") or "").strip()

    buf.extend((f"No. Tiket  : {kode}\n").encode("cp437", errors="replace"))
    buf.extend((f"Pelanggan  : {nama_cust}\n").encode("cp437", errors="replace"))
    buf.extend((f"No. HP/WA  : {no_hp}\n").encode("cp437", errors="replace"))
    buf.extend(div_line.encode("cp437"))
    buf.extend((f"Perangkat  : {perangkat}\n").encode("cp437", errors="replace"))
    buf.extend((f"Merk/Model : {unit}\n").encode("cp437", errors="replace"))
    buf.extend((f"Layanan    : {layanan}\n").encode("cp437", errors="replace"))
    buf.extend((f"Keluhan    : {keluhan}\n").encode("cp437", errors="replace"))
    if catatan_tek:
        buf.extend((f"Catatan T. : {catatan_tek}\n").encode("cp437", errors="replace"))

    buf.extend(div_line.encode("cp437"))

    # Bagian Keuangan / Biaya
    def make_two_col(left_str: str, right_str: str, width: int) -> str:
        space = width - len(left_str) - len(right_str)
        if space < 1:
            space = 1
        return left_str + (" " * space) + right_str + "\n"

    est_biaya = float(s.get("estimasi_biaya", 0) or 0)
    biaya_akhir = float(s.get("biaya_akhir", est_biaya) or 0)
    status_bayar = str(s.get("status_pembayaran") or "Belum Bayar").strip()
    sparepart_nama = str(s.get("sparepart_nama") or "").strip()
    sparepart_biaya = float(s.get("sparepart_biaya", 0) or 0)

    if is_ambil:
        if est_biaya > 0:
            est_formatted = f"Rp {int(est_biaya):,}".replace(",", ".")
            buf.extend(make_two_col("Estimasi Awal", est_formatted, col_width).encode("cp437"))
        if sparepart_nama and sparepart_biaya > 0:
            spp_formatted = f"Rp {int(sparepart_biaya):,}".replace(",", ".")
            buf.extend(make_two_col(f"Part: {sparepart_nama[:16]}", spp_formatted, col_width).encode("cp437"))

        buf.extend(BOLD_ON)
        tot_formatted = f"Rp {int(biaya_akhir):,}".replace(",", ".")
        buf.extend(make_two_col("TOTAL AKHIR", tot_formatted, col_width).encode("cp437"))
        buf.extend(make_two_col("STATUS BAYAR", status_bayar.upper(), col_width).encode("cp437"))
        buf.extend(BOLD_OFF)
    else:
        buf.extend(BOLD_ON)
        est_formatted = f"Rp {int(est_biaya):,}".replace(",", ".")
        buf.extend(make_two_col("ESTIMASI BIAYA", est_formatted, col_width).encode("cp437"))
        buf.extend(make_two_col("STATUS TIKET", str(s.get("status_servis") or "Baru").upper(), col_width).encode("cp437"))
        buf.extend(BOLD_OFF)

    buf.extend(dbl_line.encode("cp437"))

    # Footer Pesan & Syarat
    buf.extend(ALIGN_CENTER)
    if is_ambil:
        buf.extend(b"* Terima kasih atas kepercayaan Anda *\n")
        buf.extend(b"* Garansi servis 7 hari kerusakan sama *\n")
    else:
        buf.extend(b"* Simpan nota ini sebagai bukti tanda terima *\n")
        buf.extend(b"* Wajib dibawa saat pengambilan unit *\n")

    buf.extend(b"\n")
    # Slot Tanda Tangan
    if col_width >= 48:
        buf.extend(b"       Pelanggan                       Kasir/Teknisi\n\n\n")
        cust_trim = (nama_cust[:20] if nama_cust else "...............").center(20)
        buf.extend((f" ({cust_trim})                  (....................)\n").encode("cp437", errors="replace"))
    else:
        buf.extend(b" Pelanggan            Teknisi\n\n\n")
        cust_trim = (nama_cust[:14] if nama_cust else "............").center(14)
        buf.extend((f"({cust_trim})     (............)\n").encode("cp437", errors="replace"))

    buf.extend(b"\n\n\n")
    buf.extend(CUT_PAPER)

    return bytes(buf)


# ========================================================
# TSPL & ESC/POS FORMATTER UNTUK LABEL STIKER UNIT
# ========================================================

def format_tspl_label(service_dict: dict, label_size: str = "40x30", store_profile: dict = None) -> bytes:
    """
    Menghasilkan kode perintah TSPL murni (Taiwan Semiconductor Page Language)
    khusus untuk printer label stiker (seperti XP-365B, 80Label, Gprinter, TSC dll).
    Mengontrol sensor gap stiker sehingga cetakan pas di tengah stiker tanpa selip!
    """
    s = service_dict or {}
    prof = store_profile or {}

    parts = str(label_size).split("x")
    w_mm = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 40
    h_mm = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30

    kode = str(s.get("kode_servis") or f"#{s.get('id', '')}").strip()
    tgl = str(s.get("tanggal_masuk") or datetime.date.today().strftime("%Y-%m-%d"))[:10]
    nama_cust = str(s.get("nama_pelanggan") or "-")[:18]
    no_hp = str(s.get("no_hp") or "-")[:15]
    unit = str(s.get("merk_model") or "-")[:20]
    perangkat = str(s.get("jenis_perangkat") or "")[:12]
    keluhan = str(s.get("keluhan") or "-")[:22]
    st_name = (prof.get("name") or "KasToko").strip()[:16]

    tspl = []
    tspl.append(f"SIZE {w_mm} mm, {h_mm} mm")
    tspl.append("GAP 2 mm, 0 mm")
    tspl.append("DIRECTION 1")
    tspl.append("REFERENCE 0,0")
    tspl.append("OFFSET 0 mm")
    tspl.append("SET PEEL OFF")
    tspl.append("SET CUTTER OFF")
    tspl.append("SET TEAR ON")
    tspl.append("CLS")

    # Layout koordinat (DPI 203: 1mm = 8 dots)
    # Header: Kode Servis Tiket
    if h_mm >= 30:
        tspl.append(f'TEXT 15,15,"3",0,1,1,"[{kode}]"')
        tspl.append(f'TEXT 15,50,"2",0,1,1,"Tgl : {tgl}"')
        tspl.append(f'TEXT 15,75,"2",0,1,1,"Nama: {nama_cust}"')
        tspl.append(f'TEXT 15,100,"2",0,1,1,"HP  : {no_hp}"')
        tspl.append(f'TEXT 15,125,"2",0,1,1,"Unit: {unit}"')
        tspl.append(f'TEXT 15,150,"2",0,1,1,"Klh : {keluhan}"')
        tspl.append(f'TEXT 15,180,"1",0,1,1,"* {st_name} Servis *"')
    else:
        # Mini 40x20
        tspl.append(f'TEXT 10,10,"3",0,1,1,"[{kode}]"')
        tspl.append(f'TEXT 10,45,"2",0,1,1,"{nama_cust} ({no_hp})"')
        tspl.append(f'TEXT 10,70,"2",0,1,1,"Unit: {unit}"')
        tspl.append(f'TEXT 10,95,"2",0,1,1,"Klh : {keluhan}"')

    tspl.append("PRINT 1,1\n")
    return "\r\n".join(tspl).encode("ascii", errors="replace")

def format_escpos_label(service_dict: dict, label_size: str = "40x30", store_profile: dict = None) -> bytes:
    """Fallback ESC/POS untuk label stiker jika printer label dalam mode ESC/POS biasa."""
    s = service_dict or {}
    prof = store_profile or {}

    ESC = b"\x1B"
    GS = b"\x1D"
    INIT = ESC + b"\x40"
    ALIGN_LEFT = ESC + b"\x61\x00"
    ALIGN_CENTER = ESC + b"\x61\x01"
    BOLD_ON = ESC + b"\x45\x01"
    BOLD_OFF = ESC + b"\x45\x00"
    DOUBLE_STRIKE_ON = ESC + b"\x47\x01"
    CUT_PAPER = GS + b"\x56\x41\x02"

    kode = str(s.get("kode_servis") or f"#{s.get('id', '')}").strip()
    tgl = str(s.get("tanggal_masuk") or datetime.date.today().strftime("%Y-%m-%d"))[:10]
    nama_cust = str(s.get("nama_pelanggan") or "-")
    no_hp = str(s.get("no_hp") or "-")
    unit = str(s.get("merk_model") or "-")
    perangkat = str(s.get("jenis_perangkat") or "")
    keluhan = str(s.get("keluhan") or "-")
    st_name = (prof.get("name") or "KasToko").strip()

    buf = bytearray()
    buf.extend(INIT)
    buf.extend(DOUBLE_STRIKE_ON)
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON)
    buf.extend((f"[{kode}]\n").encode("cp437", errors="replace"))
    buf.extend(BOLD_OFF)
    buf.extend(ALIGN_LEFT)
    buf.extend((f"Tgl : {tgl}\n").encode("cp437", errors="replace"))
    buf.extend((f"Nama: {nama_cust}\n").encode("cp437", errors="replace"))
    if no_hp and no_hp != "-":
        buf.extend((f"HP  : {no_hp}\n").encode("cp437", errors="replace"))
    buf.extend((f"Unit: {unit} ({perangkat})\n").encode("cp437", errors="replace"))
    buf.extend((f"Klh : {keluhan}\n").encode("cp437", errors="replace"))
    buf.extend(b"--------------------------------\n")
    buf.extend(ALIGN_CENTER)
    buf.extend((f"* {st_name} *\n").encode("cp437", errors="replace"))
    buf.extend(b"\n\n")
    buf.extend(CUT_PAPER)

    return bytes(buf)

def format_receipt_test_page(printer_name: str, paper_width: str = "58", density: str = "high") -> bytes:
    """Menghasilkan nota uji coba (Test Print) untuk memverifikasi koneksi printer nota."""
    col_width = 48 if str(paper_width) == "80" else 32
    div_line = ("-" * col_width) + "\n"
    dbl_line = ("=" * col_width) + "\n"
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ESC = b"\x1B"
    GS = b"\x1D"
    INIT = ESC + b"\x40"
    ALIGN_LEFT = ESC + b"\x61\x00"
    ALIGN_CENTER = ESC + b"\x61\x01"
    BOLD_ON = ESC + b"\x45\x01"
    BOLD_OFF = ESC + b"\x45\x00"
    DOUBLE_STRIKE_ON = ESC + b"\x47\x01"
    DOUBLE_HEIGHT = GS + b"\x21\x01"
    NORMAL_SIZE = GS + b"\x21\x00"
    CUT_PAPER = GS + b"\x56\x41\x03"

    buf = bytearray()
    buf.extend(INIT)
    if density in ("high", "max"):
        buf.extend(DOUBLE_STRIKE_ON)
        buf.extend(ESC + b"\x37\x07\xFE\x02")

    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON)
    buf.extend(DOUBLE_HEIGHT)
    buf.extend(b"TEST PRINT BERHASIL!\n")
    buf.extend(NORMAL_SIZE)
    buf.extend(BOLD_OFF)
    buf.extend(b"Direct Raw ESC/POS KasToko\n")
    buf.extend(dbl_line.encode("cp437"))

    buf.extend(ALIGN_LEFT)
    buf.extend((f"Printer : {printer_name}\n").encode("cp437", errors="replace"))
    buf.extend((f"Ukuran  : {paper_width} mm ({col_width} Kolom)\n").encode("cp437"))
    buf.extend((f"Waktu   : {now_str}\n").encode("cp437"))
    buf.extend(f"Density : {density.upper()} (Deep Black)\n".encode("cp437"))
    buf.extend(div_line.encode("cp437"))

    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON)
    buf.extend(b"[ OK ] HARDWARE PRINT SIAP\n")
    buf.extend(BOLD_OFF)
    buf.extend(b"Tanpa dialog Windows / 0% GDI\n")
    buf.extend(dbl_line.encode("cp437"))
    buf.extend(b"\n\n\n")
    buf.extend(CUT_PAPER)

    return bytes(buf)

def format_label_test_page(printer_name: str, label_size: str = "40x30", mode: str = "tspl") -> bytes:
    """Menghasilkan stiker uji coba (Test Print) untuk printer label stiker."""
    parts = str(label_size).split("x")
    w_mm = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 40
    h_mm = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if mode == "tspl":
        tspl = [
            f"SIZE {w_mm} mm, {h_mm} mm",
            "GAP 2 mm, 0 mm",
            "DIRECTION 1",
            "REFERENCE 0,0",
            "OFFSET 0 mm",
            "SET PEEL OFF",
            "SET CUTTER OFF",
            "SET TEAR ON",
            "CLS",
            'TEXT 15,15,"3",0,1,1,"[TEST LABEL OK]"',
            f'TEXT 15,50,"2",0,1,1,"{printer_name[:18]}"',
            f'TEXT 15,75,"2",0,1,1,"Size: {w_mm}x{h_mm} mm (TSPL)"',
            f'TEXT 15,100,"2",0,1,1,"Tgl : {now_str[:10]}"',
            f'TEXT 15,125,"2",0,1,1,"Jam : {now_str[11:]}"',
            'TEXT 15,155,"1",0,1,1,"* KasToko Direct Print *"',
            "PRINT 1,1\n"
        ]
        return "\r\n".join(tspl).encode("ascii", errors="replace")
    else:
        # ESC/POS label
        dummy = {
            "kode_servis": "TEST-LABEL",
            "nama_pelanggan": "Uji Printer Label",
            "merk_model": printer_name[:16],
            "keluhan": f"Direct ESC/POS {label_size}"
        }
        return format_escpos_label(dummy, label_size=label_size)

