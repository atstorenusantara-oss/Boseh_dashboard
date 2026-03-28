@echo off
title BOSEH V2 - SERVER DASHBOARD
color 0A
mode con: cols=65 lines=30

:: ============================================================
:: SIMPAN PATH PROJECT (folder tempat .bat ini berada)
:: ============================================================
set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo.
echo  ============================================================
echo    BOSEH V2 - BIKE SHARING DASHBOARD
echo  ============================================================
echo.
echo  [INFO] Folder: %PROJECT_DIR%
echo.

:: ============================================================
:: JALANKAN / CEK MOSQUITTO MQTT BROKER
:: ============================================================
echo  [1/3] Mengecek Mosquitto MQTT Broker...

sc query mosquitto >nul 2>&1
if %errorlevel% equ 0 (
    :: Cek apakah service sudah running
    sc query mosquitto | find "RUNNING" >nul 2>&1
    if %errorlevel% neq 0 (
        echo  [INFO] Memulai Mosquitto Service...
        net start mosquitto >nul 2>&1
        timeout /t 2 /nobreak >nul
    )
    echo  [OK] Mosquitto MQTT Broker berjalan
) else (
    :: Coba jalankan mosquitto langsung (portable / tidak sebagai service)
    tasklist | find /i "mosquitto.exe" >nul 2>&1
    if %errorlevel% neq 0 (
        echo  [INFO] Mencoba jalankan mosquitto.exe langsung...
        start /min "" mosquitto
        timeout /t 2 /nobreak >nul
        echo  [OK] Mosquitto dijalankan
    ) else (
        echo  [OK] Mosquitto sudah berjalan
    )
)

:: ============================================================
:: JALANKAN FLASK SERVER
:: ============================================================
echo.
echo  [2/3] Memulai Flask Server...
echo.

:: Jalankan Flask di background window terpisah
start "Boseh Server" /min cmd /k "cd /d "%PROJECT_DIR%" && python app.py"

:: Tunggu server siap (max 8 detik)
echo  [INFO] Menunggu server siap...
set READY=0
for /l %%i in (1,1,8) do (
    timeout /t 1 /nobreak >nul
    curl -s http://127.0.0.1:5000 >nul 2>&1
    if !READY! equ 0 (
        if %errorlevel% equ 0 (
            set READY=1
            echo  [OK] Server siap di http://127.0.0.1:5000
        ) else (
            echo  [INFO] Menunggu... %%i/8
        )
    )
)

if %READY% equ 0 (
    :: Kalau curl tidak ada, tunggu saja 5 detik
    echo  [INFO] Server sedang starting (tunggu 5 detik)...
    timeout /t 5 /nobreak >nul
)

:: ============================================================
:: BUKA CHROME MAXIMIZE OTOMATIS
:: ============================================================
echo.
echo  [3/3] Membuka Chrome Dashboard...
echo.

set "URL=http://127.0.0.1:5000"
set CHROME_FOUND=0

:: Cek lokasi Chrome yang umum
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    set CHROME_FOUND=1
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    set CHROME_FOUND=1
)
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
    set CHROME_FOUND=1
)

if %CHROME_FOUND% equ 1 (
    :: Buka Chrome dengan mode maximize + kiosk-like + start maximized
    start "" --start-maximized "%CHROME%" --start-maximized --new-window "%URL%"
    echo  [OK] Chrome dibuka: %URL%
) else (
    :: Fallback: buka dengan browser default
    echo  [!] Chrome tidak ditemukan, menggunakan browser default...
    start "" "%URL%"
    echo  [OK] Browser dibuka: %URL%
)

:: ============================================================
:: STATUS AKHIR
:: ============================================================
echo.
echo  ============================================================
echo   SERVER BERJALAN!
echo  ============================================================
echo.
echo   Dashboard : http://127.0.0.1:5000
echo   Admin     : http://127.0.0.1:5000/admin
echo   Maintenance: http://127.0.0.1:5000/maintenance
echo.
echo   Tutup window ini untuk menutup launcher.
echo   Server tetap berjalan di background.
echo.
echo   Tekan tombol apapun untuk keluar dari launcher ini...
echo  ============================================================
echo.
pause >nul
