@echo off
:: Delegator otomatis ke tools\deploy_ke_ubuntu.bat
cd /d "%~dp0"
call tools\deploy_ke_ubuntu.bat %*
