@echo off
title BOSEH V2 - INSTALASI PC BARU
color 0A
mode con: cols=70 lines=40

echo.
echo  ============================================================
echo    ____   ___  ____  _____ _   _   __     ______
echo   | __ ) / _ \/ ___|| ____| | | | \ \   / /___ /
echo   |  _ \| | | \___ \|  _| | |_| |  \ \ / /  |_ \
echo   | |_) | |_| |___) | |___|  _  |   \ V /  ___) |
echo   |____/ \___/|____/|_____|_| |_|    \_/  |____/
echo.
echo           SCRIPT INSTALASI OTOMATIS - PC BARU
echo  ============================================================
echo.

:: Simpan direktori project
set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo  [INFO] Direktori Project: %PROJECT_DIR%
echo.

:: ============================================================
:: CEK ADMINISTRATOR
:: ============================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Script harus dijalankan sebagai ADMINISTRATOR!
    echo  [!] Klik kanan file ini, pilih "Run as administrator"
    echo.
    pause
    exit /b 1
)
echo  [OK] Berjalan sebagai Administrator

:: ============================================================
:: CEK PYTHON
:: ============================================================
echo.
echo  [1/5] Mengecek Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Python tidak ditemukan!
    echo  [!] Silakan download dan install Python 3.10+ dari:
    echo      https://www.python.org/downloads/
    echo  [!] Pastikan centang "Add Python to PATH" saat install!
    echo.
    pause
    exit /b 1
)
python --version
echo  [OK] Python ditemukan

:: ============================================================
:: INSTALL PIP PACKAGES
:: ============================================================
echo.
echo  [2/5] Menginstall package Python (flask, mqtt, qrcode, dll)...
pip install -r "%PROJECT_DIR%\requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo  [!] Gagal install packages! Cek koneksi internet.
    pause
    exit /b 1
)
echo  [OK] Semua package berhasil diinstall

:: ============================================================
:: CEK / INSTALL MOSQUITTO (MQTT BROKER)
:: ============================================================
echo.
echo  [3/5] Mengecek Mosquitto MQTT Broker...

sc query mosquitto >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Mosquitto sudah terinstall sebagai service
    goto :mosquitto_done
)

:: Cek apakah mosquitto.exe ada di PATH
mosquitto -v >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Mosquitto ditemukan di PATH
    goto :install_mosquitto_service
)

echo  [!] Mosquitto TIDAK ditemukan!
echo.
echo  Pilihan:
echo  [1] Saya akan install Mosquitto manual (lanjut ke langkah berikutnya)
echo  [2] Download Mosquitto sekarang (buka browser)
echo.
set /p MQTT_CHOICE="Pilih [1/2]: "
if "%MQTT_CHOICE%"=="2" (
    echo  Membuka halaman download Mosquitto...
    start https://mosquitto.org/download/
    echo.
    echo  Setelah install Mosquitto, jalankan ulang script ini!
    pause
    exit /b 0
)
echo  [!] Mosquitto belum terinstall. MQTT tidak akan berfungsi.
echo  [!] Lanjutkan dengan risiko sendiri...
goto :mosquitto_done

:install_mosquitto_service
echo  [INFO] Mendaftarkan Mosquitto sebagai Windows Service...
mosquitto install >nul 2>&1
net start mosquitto >nul 2>&1
echo  [OK] Mosquitto Service dijalankan

:mosquitto_done

:: ============================================================
:: SETUP AUTORUN - TASK SCHEDULER
:: ============================================================
echo.
echo  [4/5] Membuat Autorun via Task Scheduler Windows...

:: Hapus task lama jika ada
schtasks /delete /tn "BosehV2_Autorun" /f >nul 2>&1

:: Buat Task Scheduler untuk autorun saat startup
schtasks /create /tn "BosehV2_Autorun" /tr "\"%PROJECT_DIR%\START_BOSEH.bat\"" /sc ONSTART /ru SYSTEM /rl HIGHEST /f >nul 2>&1

if %errorlevel% equ 0 (
    echo  [OK] Autorun berhasil dibuat via Task Scheduler
    echo  [OK] Server akan otomatis berjalan saat Windows startup
) else (
    echo  [!] Gagal buat Task Scheduler. Coba jalankan manual.
)

:: ============================================================
:: BUAT SHORTCUT DESKTOP
:: ============================================================
echo.
echo  [5/5] Membuat Shortcut di Desktop...

set "SHORTCUT_PATH=%USERPROFILE%\Desktop\Boseh Dashboard.lnk"
set "VBS_TEMP=%TEMP%\make_shortcut.vbs"

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS_TEMP%"
echo sLinkFile = "%SHORTCUT_PATH%" >> "%VBS_TEMP%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS_TEMP%"
echo oLink.TargetPath = "%PROJECT_DIR%\START_BOSEH.bat" >> "%VBS_TEMP%"
echo oLink.WorkingDirectory = "%PROJECT_DIR%" >> "%VBS_TEMP%"
echo oLink.WindowStyle = 1 >> "%VBS_TEMP%"
echo oLink.Description = "Boseh V2 Dashboard" >> "%VBS_TEMP%"
echo oLink.Save >> "%VBS_TEMP%"
cscript //nologo "%VBS_TEMP%"
del "%VBS_TEMP%" >nul 2>&1

echo  [OK] Shortcut "Boseh Dashboard" dibuat di Desktop

:: ============================================================
:: SELESAI
:: ============================================================
echo.
echo  ============================================================
echo   INSTALASI SELESAI!
echo  ============================================================
echo.
echo   Yang sudah dilakukan:
echo   [v] Python packages terinstall
echo   [v] Mosquitto MQTT Broker dicek
echo   [v] Autorun saat startup dikonfigurasi
echo   [v] Shortcut di Desktop dibuat
echo.
echo   CARA MENJALANKAN:
echo   - Double klik "Boseh Dashboard" di Desktop, ATAU
echo   - Double klik file START_BOSEH.bat, ATAU
echo   - Restart PC (auto start)
echo.
echo  ============================================================
echo.
set /p LANGSUNG="Jalankan Boseh sekarang? [Y/N]: "
if /i "%LANGSUNG%"=="Y" (
    start "" "%PROJECT_DIR%\START_BOSEH.bat"
)
echo.
pause
