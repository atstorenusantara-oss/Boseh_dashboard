@echo off
title BOSEH V2 - STOP SERVER
color 0C
mode con: cols=55 lines=20

echo.
echo  =============================================
echo    BOSEH V2 - MENGHENTIKAN SERVER
echo  =============================================
echo.

echo  [1/2] Menghentikan Flask Server (python app.py)...
taskkill /f /im python.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Python/Flask dihentikan
) else (
    echo  [!] Tidak ada proses Python yang berjalan
)

echo.
echo  [2/2] Menghentikan Mosquitto...
net stop mosquitto >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Mosquitto dihentikan
) else (
    taskkill /f /im mosquitto.exe >nul 2>&1
    echo  [OK] Mosquitto process dihentikan
)

echo.
echo  =============================================
echo   Semua service Boseh sudah dihentikan!
echo  =============================================
echo.
timeout /t 3
