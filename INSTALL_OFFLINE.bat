@echo off
title BOSEH V2 - INSTALASI OFFLINE
color 0B
mode con: cols=80 lines=45

echo.
echo  ============================================================
echo    ____   ___  ____  _____ _   _   __     ______  
echo   | __ ) / _ \/ ___|| ____| | | | \ \   / /___ /  
echo   |  _ \| | | \___ \|  _| | |_| |  \ \ / /  |_ \  
echo   | |_) | |_| |___) | |___|  _  |   \ V /  ___) | 
echo   |____/ \___/|____/|_____|_| |_|    \_/  |____/  
echo.
echo           SCRIPT INSTALASI OFFLINE (FULL PACKAGE)
echo  ============================================================
echo.

:: Simpan direktori project
set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

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
:: 1. INSTALL PYTHON (JIKA BELUM ADA)
:: ============================================================
echo.
echo  [1/5] Mengecek Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INFO] Python tidak ditemukan. Menjalankan installer lokal...
    echo  [WARN] PASTIKAN CENTANG "Add Python to PATH" pada installer!
    start /wait "" "%PROJECT_DIR%\offline_setup\installers\python-3.12.2-amd64.exe"
    
    :: Cek lagi setelah install
    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo  [!] Python tetap tidak ditemukan atau install dibatalkan.
        echo  [!] Mohon install Python secara manual dan coba lagi.
        pause
        exit /b 1
    )
)
python --version
echo  [OK] Python siap

:: ============================================================
:: 2. INSTALL LIBRARIES (OFFLINE)
:: ============================================================
echo.
echo  [2/5] Menginstall package Python dari folder LOKAL...
python -m pip install --no-index --find-links="%PROJECT_DIR%\offline_setup\libs" -r "%PROJECT_DIR%\requirements.txt"
if %errorlevel% neq 0 (
    echo  [!] Gagal install packages dari folder lokals!
    echo  [!] Pastikan isi folder "offline_setup\libs" lengkap.
    pause
    exit /b 1
)
echo  [OK] Semua library berhasil diinstall secara offline

:: ============================================================
:: 3. INSTALL MOSQUITTO (JIKA BELUM ADA)
:: ============================================================
echo.
echo  [3/5] Mengecek Mosquitto MQTT Broker...
sc query mosquitto >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Mosquitto sudah terinstall
) else (
    echo  [INFO] Mosquitto tidak ditemukan. Menjalankan installer lokal...
    start /wait "" "%PROJECT_DIR%\offline_setup\installers\mosquitto-2.0.18-install-windows-x64.exe"
    
    :: Coba daftarkan service jika installer tidak melakukannya otomatis
    if exist "C:\Program Files\mosquitto\mosquitto.exe" (
        cd /d "C:\Program Files\mosquitto"
        mosquitto install >nul 2>&1
        net start mosquitto >nul 2>&1
        cd /d "%PROJECT_DIR%"
        echo  [OK] Mosquitto Service berhasil dikonfigurasi
    ) else (
        echo  [WARN] Mosquitto mungkin terinstall di folder non-default.
        echo  [WARN] Pastikan Mosquitto bisa dijalankan secara manual.
    )
)

:: ============================================================
:: 4. SETUP AUTORUN
:: ============================================================
echo.
echo  [4/5] Membuat Autorun via Task Scheduler...
schtasks /delete /tn "BosehV2_Autorun" /f >nul 2>&1
schtasks /create /tn "BosehV2_Autorun" /tr "\"%PROJECT_DIR%\START_BOSEH.bat\"" /sc ONSTART /ru SYSTEM /rl HIGHEST /f >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Autorun berhasil dikonfigurasi
) else (
    echo  [!] Gagal membuat Task Scheduler.
)

:: ============================================================
:: 5. BUAT SHORTCUT DESKTOP
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
echo  [OK] Shortcut "Boseh Dashboard" dibuat

:: ============================================================
:: SELESAI
:: ============================================================
echo.
echo  ============================================================
echo   INSTALASI OFFLINE SELESAI!
echo  ============================================================
echo.
echo   Seluruh komponen telah diinstall dari folder lokal.
echo   Anda tidak memerlukan koneksi internet lagi.
echo.
set /p LANGSUNG="Jalankan Boseh sekarang? [Y/N]: "
if /i "%LANGSUNG%"=="Y" (
    start "" "%PROJECT_DIR%\START_BOSEH.bat"
)
exit /b 0
