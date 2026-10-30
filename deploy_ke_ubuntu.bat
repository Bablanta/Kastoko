@echo off
title Deploy dan Sinkronisasi KasToko ke Server Ubuntu
color 0B
cd /d "%~dp0"

echo ======================================================================
echo           AUTOCASH - DEPLOY DAN SINKRONISASI SERVER UBUNTU
echo                          (192.168.1.8)
echo ======================================================================
echo.
echo  Pilih tindakan yang ingin dilakukan:
echo.
echo    [1] Update Lengkap: Kode Fitur + Database Pembukuan (Rekomendasi)
echo    [2] Update Kode dan Fitur Saja (Database server tidak diubah)
echo    [3] Ambil Database dari Server Ubuntu ke PC Lokal (Tarik Data Kasir)
echo    [4] Push ke GitHub + Update Server Ubuntu
echo    [5] Batal
echo.
set /p PILIHAN="Masukkan nomor pilihan [Default: 1]: "

if "%PILIHAN%"=="" set PILIHAN=1

if "%PILIHAN%"=="1" (
    echo.
    python deploy_manager.py full
    goto SELESAI
)

if "%PILIHAN%"=="2" (
    echo.
    python deploy_manager.py code
    goto SELESAI
)

if "%PILIHAN%"=="3" (
    echo.
    python deploy_manager.py pull_db
    goto SELESAI
)

if "%PILIHAN%"=="4" (
    echo.
    echo Mendorong perubahan ke GitHub...
    git push origin main
    echo.
    python deploy_manager.py full
    goto SELESAI
)

if "%PILIHAN%"=="5" (
    echo Dibatalkan.
    exit /b 0
)

echo Pilihan tidak valid.

:SELESAI
echo.
pause
