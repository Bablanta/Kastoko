@echo off
title Deploy Langsung ke Server Ubuntu (100% Offline LAN)
color 0A
cd /d "%~dp0"

python sync_direct_lan.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ======================================================================
    echo [GAGAL] Deploy langsung tidak berhasil.
    echo Pastikan server Ubuntu 192.168.1.8 menyala dan terhubung dalam 1 WiFi.
    echo ======================================================================
)

echo.
pause
