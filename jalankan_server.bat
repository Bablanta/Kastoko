@echo off
title KasToko - Server Pembukuan Toko
color 0A

:: Otomatis izinkan firewall untuk port 8080
netsh advfirewall firewall add rule name="Python HTTP Server 8080" dir=in action=allow protocol=TCP localport=8080 >nul 2>&1

cd /d "%~dp0"

echo ======================================================================
echo                      KASTOKO - SERVER PEMBUKUAN
echo ======================================================================
echo  Server sedang aktif pada: http://localhost:8080
echo.
echo  PETUNJUK:
echo  - Jendela ini TIDAK lagi auto-hide saat dibuka.
echo  - Jika jendela ini di-MINIMIZE (klik tombol _ di pojok kanan atas),
echo    jendela akan otomatis disembunyikan ke System Tray (Background).
echo  - Ikon KasToko (KT) akan aktif di System Tray notification area.
echo  - Klik kanan ikon Tray untuk:
echo      * Open  : Membuka dashboard KasToko di browser ^& pulihkan jendela
echo      * Quit  : Menghentikan server dan keluar
echo ======================================================================
echo.

python server.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Terjadi kesalahan saat menjalankan server.
    pause
)
