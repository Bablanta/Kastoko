@echo off
title Aplikasi Pembukuan Toko - Background Server
color 0A

:: Otomatis buka Firewall untuk port 8080
netsh advfirewall firewall add rule name="Python HTTP Server 8080" dir=in action=allow protocol=TCP localport=8080 >nul 2>&1

:: Jalankan secara tersembunyi di background tanpa membuat file tambahan
if "%1"=="h" goto 1
mshta vbscript:createobject("wscript.shell").run("""%~f0"" h",0)(window.close)
exit
:1

cd /d "%~dp0"
python server.py
