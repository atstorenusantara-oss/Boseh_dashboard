@echo off
echo ============================================================
echo   MENGKOMPILASI BOSEH DASHBOARD V2 KE DESKTOP APP (.EXE)
echo ============================================================
echo.
echo Mode: Single Window (Tanpa Browser)
echo Menjalankan PyInstaller...
echo.

:: Menambahkan --collect-all webview jika diperlukan, tapi biasanya pyinstaller menemukannya
pyinstaller --noconfirm --name "Boseh_App" --onefile --windowed ^
--add-data "templates;templates" ^
--add-data "static;static" ^
--add-data "sub_programPY;sub_programPY" ^
--icon "static/img/dishub_logo.png" ^
app.py

echo.
echo ============================================================
echo   KOMPILASI SELESAI! 
echo   File: dist\Boseh_App.exe
echo ============================================================
pause
