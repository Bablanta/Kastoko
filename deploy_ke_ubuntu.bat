@echo off
title Deploy KasToko ke Server Ubuntu (192.168.1.8)
color 0B
cd /d "%~dp0"

echo ======================================================================
echo             DEPLOY KASTOKO KE SERVER UBUNTU (192.168.1.8)
echo ======================================================================
echo.

echo [1/3] Memeriksa status git lokal...
git status -s
echo.

echo [2/3] Mendorong (push) commit terbaru ke GitHub...
git push origin main
if %ERRORLEVEL% NEQ 0 (
    echo [PERINGATAN] Git push menemui kendala. Mencoba melanjutkan deploy...
)
echo.

echo [3/3] Menghubungi server Ubuntu via SSH dan memperbarui KasToko...
ssh -o StrictHostKeyChecking=accept-new bablanta@192.168.1.8 "/home/bablanta/Kastoko/deploy.sh"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ======================================================================
    echo [GAGAL] Tidak dapat menghubungi server Ubuntu 192.168.1.8 via SSH!
    echo Pastikan komputer Ubuntu hidup dan terhubung ke jaringan Wi-Fi/LAN.
    echo ======================================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo   [BERHASIL] KASTOKO DI SERVER UBUNTU TELAH DIPERBARUI DAN RESTART!
echo   Akses di browser: http://192.168.1.8:8080
echo ======================================================================
echo.

pause
