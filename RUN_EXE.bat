@echo off
title Boseh Desktop App Launcher
echo ============================================================
echo   MENJALANKAN BOSEH DASHBOARD (DESKTOP MODE)
echo ============================================================
echo.

if exist "dist\Boseh_App.exe" (
    echo Memulai aplikasi dari folder dist...
    start dist\Boseh_App.exe
) else if exist "Boseh_App.exe" (
    echo Memulai aplikasi...
    start Boseh_App.exe
) else (
    echo [ERROR] Boseh_App.exe tidak ditemukan. 
    echo Pastikan Anda sudah menjalankan BUILD_EXE.bat.
    pause
)
