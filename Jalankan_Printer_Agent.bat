@echo off
chcp 65001 >nul
title KasToko - Local Printer Agent
color 0A

cd /d "%~dp0"
echo ================================================================
echo          KASTOKO - LOCAL HARDWARE PRINTER AGENT
echo ================================================================
echo Menghubungkan printer fisik di PC ini ke aplikasi KasToko...
echo.

if exist "%~dp0KasToko_Printer_Agent.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0KasToko_Printer_Agent.ps1"
) else if exist "%~dp0tools\KasToko_Printer_Agent.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\KasToko_Printer_Agent.ps1"
) else (
    echo [ERROR] File KasToko_Printer_Agent.ps1 tidak ditemukan!
    pause
    exit /b 1
)

if %errorlevel% neq 0 (
    echo.
    echo Agen printer berhenti dengan kode %errorlevel%.
    pause
)
