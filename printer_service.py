# -*- coding: utf-8 -*-
"""
printer_service.py - Module Direct Raw Printing via Windows Spooler API (winspool.drv)
0% .NET Framework dependency - Native Win32 C ABI via CPython ctypes.
"""

import ctypes
from ctypes import wintypes
import datetime
import io
import base64

try:
    from PIL import Image
except ImportError:
    Image = None

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
    st_name = (prof.get("name") or "DHANZCELL SMARTPHONE").strip()
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
    sparepart_nama = str(s.get("sparepart_nama") or "").strip()

    buf.extend((f"No. Tiket  : {kode}\n").encode("cp437", errors="replace"))
    buf.extend((f"Pelanggan  : {nama_cust}\n").encode("cp437", errors="replace"))
    buf.extend((f"No. HP/WA  : {no_hp}\n").encode("cp437", errors="replace"))
    buf.extend(div_line.encode("cp437"))
    buf.extend((f"Perangkat  : {perangkat}\n").encode("cp437", errors="replace"))
    buf.extend((f"Merk/Model : {unit}\n").encode("cp437", errors="replace"))
    imei_sn = str(s.get("imei_sn") or "").strip()
    if imei_sn:
        buf.extend((f"IMEI / SN  : {imei_sn}\n").encode("cp437", errors="replace"))
    buf.extend((f"Layanan    : {layanan}\n").encode("cp437", errors="replace"))
    buf.extend((f"Keluhan    : {keluhan}\n").encode("cp437", errors="replace"))
    if catatan_tek:
        buf.extend((f"Catatan Tek: {catatan_tek}\n").encode("cp437", errors="replace"))
    if sparepart_nama:
        buf.extend((f"Sparepart  : {sparepart_nama}\n").encode("cp437", errors="replace"))

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
    sparepart_biaya = float(s.get("sparepart_biaya", 0) or 0)

    if is_ambil:
        if est_biaya > 0:
            est_formatted = f"Rp {int(est_biaya):,}".replace(",", ".")
            buf.extend(make_two_col("Estimasi Awal", est_formatted, col_width).encode("cp437"))

        buf.extend(BOLD_ON)
        tot_formatted = f"Rp {int(biaya_akhir):,}".replace(",", ".")
        buf.extend(make_two_col("TOTAL BIAYA", tot_formatted, col_width).encode("cp437"))
        garansi_text = str(s.get("garansi") or "7 Hari").strip()
        buf.extend(make_two_col("STATUS BAYAR", f"{status_bayar.upper()} ({garansi_text})", col_width).encode("cp437"))
        buf.extend(BOLD_OFF)
    else:
        buf.extend(BOLD_ON)
        est_formatted = f"Rp {int(est_biaya):,}".replace(",", ".")
        buf.extend(make_two_col("ESTIMASI BIAYA", est_formatted, col_width).encode("cp437"))
        buf.extend(make_two_col("STATUS SERVIS", str(s.get("status_servis") or "Baru").upper(), col_width).encode("cp437"))
        buf.extend(BOLD_OFF)

    buf.extend(dbl_line.encode("cp437"))

    # Footer Pesan & Syarat
    buf.extend(ALIGN_CENTER)
    if is_ambil:
        buf.extend(b"* Unit telah diterima dlm kondisi baik & normal *\n")
        buf.extend(b"* Simpan nota ini sebagai bukti sah garansi *\n")
    else:
        buf.extend(b"* Simpan nota ini sebagai tanda bukti resmi *\n")
        buf.extend(b"* Kerusakan aksesoris tidak tercatat di luar tg jawab *\n")

    # QR Code Pelacakan Servisan Online (Khusus Nota Penerimaan Unit)
    if not is_ambil and kode:
        tracking_url = f"https://lacak.dhanzcell.my.id/lacak?nota={kode}"
        qr_bytes = tracking_url.encode("ascii", errors="replace")
        
        buf.extend(ALIGN_CENTER)
        buf.extend(b"\n[ SCAN CEK STATUS SERVIS ]\n")
        
        # ESC/POS QR Code Model 2, Module Size 4/5, Error Correction M
        # 1. Set QR model 2
        buf.extend(b"\x1D\x28\x6B\x04\x00\x31\x41\x32\x00")
        # 2. Set module size (4 for 58mm, 5 for 80mm)
        # 2. Set module size (4 for 80x100mm thermal label height optimization)
        mod_size = b"\x04"
        buf.extend(b"\x1D\x28\x6B\x03\x00\x31\x43" + mod_size)
        # 3. Set error correction level M
        buf.extend(b"\x1D\x28\x6B\x03\x00\x31\x45\x31")
        # 4. Store QR data
        len_qr = len(qr_bytes) + 3
        pL = len_qr % 256
        pH = len_qr // 256
        buf.extend(bytes([0x1D, 0x28, 0x6B, pL, pH, 0x31, 0x50, 0x30]) + qr_bytes)
        # 5. Print QR Code
        buf.extend(b"\x1D\x28\x6B\x03\x00\x31\x51\x30")
        buf.extend(b"lacak.dhanzcell.my.id\n")
        buf.extend(div_line.encode("cp437"))

    buf.extend(b"\n")
    # Slot Tanda Tangan
    if col_width >= 48:
        buf.extend(b"       Pelanggan                       Kasir/Teknisi\n\n")
        cust_trim = (nama_cust[:20] if nama_cust else "...............").center(20)
        buf.extend((f" ({cust_trim})                  (....................)\n").encode("cp437", errors="replace"))
    else:
        buf.extend(b" Pelanggan            Teknisi\n\n")
        cust_trim = (nama_cust[:14] if nama_cust else "............").center(14)
        buf.extend((f"({cust_trim})     (............)\n").encode("cp437", errors="replace"))

    buf.extend(b"\n")
    buf.extend(CUT_PAPER)

    return bytes(buf)


# ========================================================
# TSPL FORMATTER UNTUK NOTA THERMAL LABEL 78 x 98 MM
# ========================================================

def format_tspl_receipt(service_dict: dict, store_profile: dict = None, is_ambil: bool = False, width_mm: int = 78, height_mm: int = 98) -> bytes:
    """
    Format Nota Tanda Terima / Pengambilan Servis dalam bahasa TSPL murni
    untuk printer thermal label (seperti 80Label, XP-365B, Gprinter, TSC dll) ukuran 78 x 98 mm.
    Presisi 100% pada celah (gap) stiker label tanpa selip atau terpotong!
    Margin mentok kiri (0 offset) dan batas kanan aman di dalam printhead 72mm.
    """
    s = service_dict or {}
    prof = store_profile or {}

    total_w = 560  # 70 mm (560 dots) aman di dalam lebar fisik printhead 72mm (576 dots)
    total_h = int(height_mm * 8)  # 784 dots untuk 98mm

    tspl = []
    tspl.append(f"SIZE {width_mm} mm, {height_mm} mm")
    tspl.append("GAP 2 mm, 0 mm")
    tspl.append("DIRECTION 1")
    tspl.append("REFERENCE 0,0")
    tspl.append("OFFSET 0 mm")
    tspl.append("SET PEEL OFF")
    tspl.append("SET CUTTER OFF")
    tspl.append("SET TEAR ON")
    tspl.append("CLS")

    def center_x(txt, fw):
        w = len(txt) * fw
        return max(0, (total_w - w) // 2)

    y = 2

    # 1. Header Toko (Rata Kiri, Mentok Atas Y=2)
    st_name = (prof.get("name") or "DHANZCELL SMARTPHONE").strip().upper()
    tspl.append(f'TEXT 0,{y},"3",0,1,1,"{st_name}"')
    y += 28

    st_addr = (prof.get("address") or "").strip()
    if st_addr:
        tspl.append(f'TEXT 0,{y},"1",0,1,1,"{st_addr[:50]}"')
        y += 18

    st_phone = (prof.get("phone") or "").strip()
    if st_phone:
        p_txt = f"Telp / WA: {st_phone}"
        tspl.append(f'TEXT 0,{y},"1",0,1,1,"{p_txt}"')
        y += 20

    # 2. Judul Nota & Garis Pembatas (Rata Kiri)
    tspl.append(f"BAR 0,{y},550,2")
    y += 8

    title = "NOTA PENGAMBILAN & KWITANSI" if is_ambil else "TANDA TERIMA PENERIMAAN UNIT"
    tspl.append(f'TEXT 0,{y},"2",0,1,1,"{title}"')
    y += 22

    kode = str(s.get("kode_servis") or f"#{s.get('id', '')}").strip()
    tgl = str(s.get("tanggal_masuk" if not is_ambil else "tanggal_selesai") or datetime.date.today().strftime("%Y-%m-%d"))[:10]
    tspl.append(f'TEXT 0,{y},"1",0,1,1,"Waktu: {tgl}"')
    y += 20

    tspl.append(f"BAR 0,{y},550,1")
    y += 8

    # 3. Rincian Pelanggan & Unit (Rata Kiri)
    tspl.append(f'TEXT 0,{y},"3",0,1,1,"No. Tiket   : {kode}"')
    y += 26

    # 4. Rincian Pelanggan & Unit (Mentok Kiri X=0)
    nama_cust = str(s.get("nama_pelanggan") or "-").strip()[:24]
    no_hp = str(s.get("no_hp") or "-").strip()[:18]
    unit = str(s.get("merk_model") or "-").strip()[:24]
    perangkat = str(s.get("jenis_perangkat") or "").strip()[:16]
    imei_sn = str(s.get("imei_sn") or "").strip()[:24]
    layanan = str(s.get("menu_servis") or "").strip()[:24]
    keluhan = str(s.get("keluhan") or "-").strip()[:34]
    catatan_tek = str(s.get("catatan_teknisi") or "").strip()
    sparepart_nama = str(s.get("sparepart_nama") or "").strip()[:26]

    tspl.append(f'TEXT 0,{y},"2",0,1,1,"Pelanggan   : {nama_cust}"')
    y += 22
    tspl.append(f'TEXT 0,{y},"2",0,1,1,"No. HP/WA   : {no_hp}"')
    y += 22
    tspl.append(f"BAR 0,{y},550,1")
    y += 8
    tspl.append(f'TEXT 0,{y},"2",0,1,1,"Perangkat   : {perangkat}"')
    y += 22
    tspl.append(f'TEXT 0,{y},"2",0,1,1,"Merk/Model  : {unit}"')
    y += 22
    if imei_sn:
        tspl.append(f'TEXT 0,{y},"2",0,1,1,"IMEI / SN   : {imei_sn}"')
        y += 22
    if layanan and layanan != "-":
        tspl.append(f'TEXT 0,{y},"2",0,1,1,"Layanan     : {layanan}"')
        y += 22
    tspl.append(f'TEXT 0,{y},"2",0,1,1,"Keluhan     : {keluhan}"')
    y += 22
    if catatan_tek:
        tspl.append(f'TEXT 0,{y},"2",0,1,1,"Catatan Tek : {catatan_tek}"')
        y += 22
    if sparepart_nama:
        tspl.append(f'TEXT 0,{y},"2",0,1,1,"Sparepart   : {sparepart_nama}"')
        y += 22

    # 5. Kotak Biaya & Status (Mentok Kiri X=0, Batas Kanan 550)
    tspl.append(f"BAR 0,{y},550,1")
    y += 6

    box_y = y
    box_h = 52
    tspl.append(f"BOX 0,{box_y},550,{box_y + box_h},2")

    est_biaya = float(s.get("estimasi_biaya", 0) or 0)
    biaya_akhir = float(s.get("biaya_akhir", est_biaya) or 0)
    status_bayar = str(s.get("status_pembayaran") or "Belum Bayar").strip()
    status_servis = str(s.get("status_servis") or "Baru").strip()

    if is_ambil:
        tot_str = f"Rp {int(biaya_akhir):,}".replace(",", ".")
        garansi = str(s.get("garansi") or "7 Hari").strip()
        tspl.append(f'TEXT 8,{box_y + 8},"3",0,1,1,"TOTAL BIAYA : {tot_str}"')
        tspl.append(f'TEXT 8,{box_y + 32},"2",0,1,1,"STATUS BAYAR: {status_bayar} (Garansi {garansi})"')
    else:
        est_str = f"Rp {int(est_biaya):,}".replace(",", ".")
        tspl.append(f'TEXT 8,{box_y + 8},"3",0,1,1,"ESTIMASI BIAYA: {est_str}"')
        tspl.append(f'TEXT 8,{box_y + 32},"2",0,1,1,"STATUS SERVIS : {status_servis}"')
    y += box_h + 8

    # 6. Syarat & Tanda Tangan + QR Code Pelacakan
    if is_ambil:
        tspl.append(f'TEXT 0,{y},"1",0,1,1,"* Unit telah diterima dlm kondisi baik & berfungsi normal."')
        y += 14
        tspl.append(f'TEXT 0,{y},"1",0,1,1,"* Simpan nota ini sebagai bukti sah garansi resmi servis."')
        y += 14
    else:
        tspl.append(f'TEXT 0,{y},"1",0,1,1,"* Simpan nota ini sebagai tanda bukti resmi saat mengambil unit."')
        y += 14
        tspl.append(f'TEXT 0,{y},"1",0,1,1,"* Kerusakan aksesoris tidak tercatat di luar tanggung jawab toko."')
        y += 14

    footer_y = y
    # Kolom Kiri: Tanda Tangan Pelanggan & Kasir (Garis Solid Minimalis)
    tspl.append(f'TEXT 25,{footer_y + 4},"1",0,1,1,"Pelanggan"')
    tspl.append(f'TEXT 165,{footer_y + 4},"1",0,1,1,"Kasir / Teknisi"')
    tspl.append(f'BAR 15,{footer_y + 52},115,1')
    tspl.append(f'BAR 155,{footer_y + 52},120,1')
    tspl.append(f'TEXT 20,{footer_y + 58},"1",0,1,1,"( {nama_cust[:12]} )"')
    tspl.append(f'TEXT 160,{footer_y + 58},"1",0,1,1,"( Dhanzcell )"')

    # Kolom Kanan: QR Code Pelacakan Online
    qr_x = 390
    tspl.append(f"BOX {qr_x - 8},{footer_y},550,{footer_y + 92},1")
    tspl.append(f'TEXT {qr_x + 12},{footer_y + 4},"1",0,1,1,"SCAN STATUS"')
    tracking_url = f"https://lacak.dhanzcell.my.id/lacak?nota={kode}"
    tspl.append(f'QRCODE {qr_x + 14},{footer_y + 18},L,3,A,0,"{tracking_url}"')
    tspl.append(f'TEXT {qr_x + 2},{footer_y + 78},"1",0,1,1,"lacak.dhanzcell"')

    tspl.append("PRINT 1,1\n")
    return "\r\n".join(tspl).encode("ascii", errors="replace")

    y = footer_y + 96
    tspl.append(f"BAR 16,{y},592,1")
    y += 8

    # 7. Penutup
    thank_txt = "* Terima Kasih atas Kepercayaan Anda *"
    tspl.append(f'TEXT {center_x(thank_txt, 8)},{y},"1",0,1,1,"{thank_txt}"')

    tspl.append("PRINT 1,1\n")
    return "\r\n".join(tspl).encode("ascii", errors="replace")


def format_image_receipt(image_data, paper_width: str = "80", is_tspl: bool = True, density: str = "high") -> bytes:
    """
    Format Nota Grafis Monokrom (Bitmap Raster) langsung dari tangkapan layar HTML.
    Menghasilkan cetakan yang 100% IDENTIK dengan gambar pratinjau di layar:
    - Logo toko di kiri tercetak tajam
    - Font modern & proporsional
    - Kotak putus-putus (dashed border), QR Code, dan tanda tangan presisi
    Mendukung TSPL (80Label/XP-365B) dan ESC/POS (POS-58 & POS-80).
    """
    if Image is None:
        raise RuntimeError("Modul Pillow (PIL) belum terpasang di sistem.")

    if isinstance(image_data, str):
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        img_bytes = base64.b64decode(image_data)
    else:
        img_bytes = image_data

    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    # Tentukan lebar dot sesuai standar printer thermal
    # TSPL 78mm -> 560 dots (70 bytes), mentok kiri (X=0) & pas di dalam printhead 72mm tanpa terpotong
    # ESC/POS 58mm -> 384 dots (48 bytes)
    # ESC/POS 80mm -> 560 dots (70 bytes)
    if is_tspl:
        target_w = 560
    elif str(paper_width) == "58":
        target_w = 384
    else:
        target_w = 560

    aspect = img.height / float(img.width)
    target_h = int(target_w * aspect)

    # Resize gambar dengan filter Lanczos untuk ketajaman teks maksimal
    resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    gray = resized.convert("L")

    # Binarisasi ke 1-bit monokrom (threshold 195)
    # Nilai < 195 menjadi hitam, >= 195 menjadi putih kertas
    table = [0 if i < 195 else 255 for i in range(256)]
    mono = gray.point(table, "1")

    w_bytes = target_w // 8
    raw_tspl = mono.tobytes()  # Dalam mode '1' PIL: 0 = hitam, 1 = putih (persis TSPL)

    if is_tspl:
        height_mm = max(90, int(round(target_h / 8.0)))
        width_mm = 78
        buf = bytearray()
        buf.extend(f"SIZE {width_mm} mm, {height_mm} mm\r\n".encode("ascii"))
        buf.extend(b"GAP 2 mm, 0 mm\r\n")
        buf.extend(b"DIRECTION 1\r\n")
        buf.extend(b"REFERENCE 0,0\r\n")
        buf.extend(b"OFFSET 0 mm\r\n")
        buf.extend(b"SET PEEL OFF\r\n")
        buf.extend(b"SET CUTTER OFF\r\n")
        buf.extend(b"SET TEAR ON\r\n")
        buf.extend(b"CLS\r\n")
        # Offset X=0 dots, Y=0 dots (MENTOK KIRI & ATAS 100% tanpa margin buang di kop)
        buf.extend(f"BITMAP 0,0,{w_bytes},{target_h},0,".encode("ascii"))
        buf.extend(raw_tspl)
        buf.extend(b"\r\nPRINT 1,1\r\n")
        return bytes(buf)
    else:
        # ESC/POS GS v 0 (1 = hitam / print dot, 0 = putih / blank)
        raw_escpos = bytes(b ^ 0xFF for b in raw_tspl)
        xL = w_bytes % 256
        xH = w_bytes // 256
        yL = target_h % 256
        yH = target_h // 256

        buf = bytearray()
        buf.extend(b"\x1B\x40")  # Reset printer
        if density in ("high", "max"):
            buf.extend(b"\x1B\x47\x01")  # Double-strike (cetak pekat)
            buf.extend(b"\x1B\x37\x07\xFE\x02")  # Heating parameter
        buf.extend(b"\x1B\x61\x00")  # Rata kiri
        buf.extend(bytes([0x1D, 0x76, 0x30, 0x00, xL, xH, yL, yH]))
        buf.extend(raw_escpos)
        buf.extend(b"\n\n\n\x1D\x56\x41\x03")  # Feed kertas & potong
        return bytes(buf)


# ========================================================
# TSPL & ESC/POS FORMATTER UNTUK LABEL STIKER UNIT
# ========================================================

def format_tspl_label(service_dict: dict, label_size: str = "40x20", store_profile: dict = None) -> bytes:
    """
    Format Label Stiker Identitas Minimalis (40x20mm / 40x30mm) dalam perintah TSPL murni:
    - Hanya 5 field identitas: No Tiket, Nama Pelanggan, No WA, Estimasi Biaya, Keluhan.
    - Tanpa kop, tanpa logo, tanpa QR code, tanpa teks redundan.
    - Margin rata kiri 2mm dan rata atas 2mm (16 dots pada 203 DPI).
    """
    s = service_dict or {}

    parts = str(label_size).split("x")
    w_mm = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 40
    h_mm = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20

    def clean_t(val, max_len=24):
        t = str(val or "-").strip().replace('"', "'")
        return t[:max_len]

    kode = clean_t(s.get("kode_servis") or f"#{s.get('id', '')}", 16)
    nama = clean_t(s.get("nama_pelanggan"), 22)
    no_wa = clean_t(s.get("no_hp"), 20)

    biaya_val = float(s.get("biaya_akhir") or s.get("estimasi_biaya") or 0)
    biaya_str = f"Rp {int(biaya_val):,}".replace(",", ".") if biaya_val > 0 else "Rp 0"
    biaya_str = clean_t(biaya_str, 20)

    keluhan = clean_t(s.get("keluhan"), 24)

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

    # Margin rata kiri 2mm = 16 dots, margin rata atas 2mm = 16 dots (DPI 203: 1mm = 8 dots)
    x = 16
    if h_mm <= 22:
        # Kertas 40x20 mm (160 dots total height):
        # 5 baris identitas murni presisi tinggi
        tspl.append(f'TEXT {x},16,"3",0,1,1,"{kode}"')
        tspl.append(f'TEXT {x},44,"2",0,1,1,"{nama}"')
        tspl.append(f'TEXT {x},68,"2",0,1,1,"{no_wa}"')
        tspl.append(f'TEXT {x},92,"2",0,1,1,"{biaya_str}"')
        tspl.append(f'TEXT {x},116,"2",0,1,1,"{keluhan}"')
    else:
        # Kertas 40x30 mm / 50x30 mm
        tspl.append(f'TEXT {x},16,"3",0,1,1,"{kode}"')
        tspl.append(f'TEXT {x},52,"2",0,1,1,"{nama}"')
        tspl.append(f'TEXT {x},86,"2",0,1,1,"{no_wa}"')
        tspl.append(f'TEXT {x},120,"2",0,1,1,"{biaya_str}"')
        tspl.append(f'TEXT {x},154,"2",0,1,1,"{keluhan}"')

    tspl.append("PRINT 1,1\n")
    return "\r\n".join(tspl).encode("ascii", errors="replace")


def format_image_label(image_data, label_size: str = "40x20", is_tspl: bool = True) -> bytes:
    """
    Format Label Stiker Grafis Monokrom (Bitmap Raster) langsung dari tangkapan layar HTML.
    Menghasilkan cetakan yang 100% IDENTIK dengan tampilan di layar (WYSIWYG):
    - Border bersih tanpa garis terpotong
    - Teks hitam solid & tajam
    - QR code presisi dapat dipindai seketika
    """
    if Image is None:
        raise RuntimeError("Modul Pillow (PIL) belum terpasang di sistem.")

    if isinstance(image_data, str):
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        img_bytes = base64.b64decode(image_data)
    else:
        img_bytes = image_data

    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    parts = str(label_size).split("x")
    w_mm = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 40
    h_mm = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30

    target_w = int(w_mm * 8)
    target_w = (target_w // 8) * 8
    target_h = int(h_mm * 8)

    resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    gray = resized.convert("L")
    table = [0 if i < 195 else 255 for i in range(256)]
    mono = gray.point(table, "1")

    w_bytes = target_w // 8
    raw_tspl = mono.tobytes()

    if is_tspl:
        buf = bytearray()
        buf.extend(f"SIZE {w_mm} mm, {h_mm} mm\r\n".encode("ascii"))
        buf.extend(b"GAP 2 mm, 0 mm\r\n")
        buf.extend(b"DIRECTION 1\r\n")
        buf.extend(b"REFERENCE 0,0\r\n")
        buf.extend(b"OFFSET 0 mm\r\n")
        buf.extend(b"SET PEEL OFF\r\n")
        buf.extend(b"SET CUTTER OFF\r\n")
        buf.extend(b"SET TEAR ON\r\n")
        buf.extend(b"CLS\r\n")
        buf.extend(f"BITMAP 0,0,{w_bytes},{target_h},0,".encode("ascii"))
        buf.extend(raw_tspl)
        buf.extend(b"\r\nPRINT 1,1\r\n")
        return bytes(buf)
    else:
        # ESC/POS GS v 0
        raw_escpos = bytes(b ^ 0xFF for b in raw_tspl)
        xL = w_bytes % 256
        xH = w_bytes // 256
        yL = target_h % 256
        yH = target_h // 256

        buf = bytearray()
        buf.extend(b"\x1B\x40")
        buf.extend(b"\x1B\x47\x01")
        buf.extend(b"\x1B\x61\x00")
        buf.extend(bytes([0x1D, 0x76, 0x30, 0x00, xL, xH, yL, yH]))
        buf.extend(raw_escpos)
        buf.extend(b"\n\n\x1D\x56\x41\x02")
        return bytes(buf)


def format_escpos_label(service_dict: dict, label_size: str = "40x20", store_profile: dict = None) -> bytes:
    """Fallback ESC/POS untuk label stiker identitas (40x20mm)."""
    s = service_dict or {}

    ESC = b"\x1B"
    GS = b"\x1D"
    INIT = ESC + b"\x40"
    ALIGN_LEFT = ESC + b"\x61\x00"
    BOLD_ON = ESC + b"\x45\x01"
    BOLD_OFF = ESC + b"\x45\x00"
    DOUBLE_STRIKE_ON = ESC + b"\x47\x01"
    CUT_PAPER = GS + b"\x56\x41\x02"

    kode = str(s.get("kode_servis") or f"#{s.get('id', '')}").strip()
    nama = str(s.get("nama_pelanggan") or "-").strip()
    no_wa = str(s.get("no_hp") or "-").strip()
    biaya_val = float(s.get("biaya_akhir") or s.get("estimasi_biaya") or 0)
    biaya_str = f"Rp {int(biaya_val):,}".replace(",", ".") if biaya_val > 0 else "Rp 0"
    keluhan = str(s.get("keluhan") or "-").strip()

    buf = bytearray()
    buf.extend(INIT)
    buf.extend(DOUBLE_STRIKE_ON)
    buf.extend(ALIGN_LEFT)
    buf.extend(BOLD_ON)
    buf.extend((f"{kode}\n").encode("cp437", errors="replace"))
    buf.extend(BOLD_OFF)
    buf.extend((f"{nama}\n").encode("cp437", errors="replace"))
    buf.extend((f"{no_wa}\n").encode("cp437", errors="replace"))
    buf.extend((f"{biaya_str}\n").encode("cp437", errors="replace"))
    buf.extend((f"{keluhan}\n").encode("cp437", errors="replace"))
    buf.extend(b"\n")
    buf.extend(CUT_PAPER)

    return bytes(buf)

def format_receipt_test_page(printer_name: str, paper_width: str = "78x98", density: str = "high") -> bytes:
    """Menghasilkan nota uji coba (Test Print) untuk memverifikasi koneksi printer nota dengan margin mentok kiri."""
    if "78" in str(paper_width) or "label" in str(printer_name).lower():
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tspl = [
            "SIZE 78 mm, 98 mm",
            "GAP 2 mm, 0 mm",
            "DIRECTION 1",
            "REFERENCE 0,0",
            "OFFSET 0 mm",
            "SET PEEL OFF",
            "SET CUTTER OFF",
            "SET TEAR ON",
            "CLS",
            'TEXT 110,20,"3",0,1,1,"TEST PRINT 78x98 MM"',
            'TEXT 135,55,"2",0,1,1,"KASTOKO DIRECT PRINT"',
            "BAR 0,85,550,2",
            f'TEXT 4,100,"2",0,1,1,"Printer : {printer_name[:24]}"',
            'TEXT 4,125,"2",0,1,1,"Format  : TSPL Label Mode (Mentok Kiri)"',
            f'TEXT 4,150,"2",0,1,1,"Waktu   : {now_str}"',
            f'TEXT 4,175,"2",0,1,1,"Status  : Siap Cetak (0% Dialog Windows)"',
            "BAR 0,205,550,1",
            "BOX 0,220,550,300,2",
            'TEXT 30,235,"3",0,1,1,"[ OK ] HARDWARE PRINT SIAP"',
            'TEXT 20,265,"2",0,1,1,"Klik Langsung Cetak - Tanpa Dialog"',
            "BAR 0,320,550,1",
            'TEXT 4,340,"1",0,1,1,"* Celah label (gap) terdeteksi otomatis oleh sensor."',
            'TEXT 4,360,"1",0,1,1,"* Pas di 1 lembar stiker tanpa tembus ke stiker berikutnya."',
            "PRINT 1,1\n"
        ]
        return "\r\n".join(tspl).encode("ascii", errors="replace")

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

def format_label_test_page(printer_name: str, label_size: str = "40x20", mode: str = "tspl") -> bytes:
    """Menghasilkan stiker uji coba (Test Print) label identitas minimalis (40x20mm)."""
    parts = str(label_size).split("x")
    w_mm = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 40
    h_mm = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20

    dummy_service = {
        "kode_servis": "SRV-20261107-004",
        "nama_pelanggan": "Tita",
        "no_hp": "08987125805",
        "estimasi_biaya": 150000,
        "keluhan": "matot"
    }
    if mode == "tspl":
        return format_tspl_label(dummy_service, label_size=f"{w_mm}x{h_mm}")
    else:
        return format_escpos_label(dummy_service, label_size=f"{w_mm}x{h_mm}")

