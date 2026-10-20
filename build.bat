@echo off
setlocal
cd /d "%~dp0"
title Halo - Build dan pasang

where py >nul 2>nul
if errorlevel 1 goto nopy

if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto nopy
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail

echo.
echo === Membuat Halo.exe (butuh beberapa menit) ===
taskkill /f /im Halo.exe >nul 2>nul
pyinstaller --noconfirm --clean --onefile --noconsole --name Halo ^
  --icon "assets\halo.ico" --add-data "assets;assets" ^
  --hidden-import winrt._winrt ^
  --hidden-import winrt._winrt_windows_foundation ^
  --hidden-import winrt._winrt_windows_foundation_collections ^
  --hidden-import winrt._winrt_windows_storage_streams ^
  --hidden-import winrt._winrt_windows_media_control ^
  --exclude-module tkinter main.py
if errorlevel 1 goto fallback
if not exist "dist\Halo.exe" goto fallback

set "INSTALL=%LOCALAPPDATA%\Halo"
mkdir "%INSTALL%" 2>nul
copy /y "dist\Halo.exe" "%INSTALL%\Halo.exe" >nul
set "TARGET=%INSTALL%\Halo.exe"
set "ARGS="
set "ICON=%INSTALL%\Halo.exe,0"
goto shortcut

:fallback
echo.
echo PyInstaller gagal - memakai shortcut ke Python (pythonw) sebagai cadangan.
set "TARGET=%CD%\.venv\Scripts\pythonw.exe"
set "ARGS=main.py"
set "ICON=%CD%\assets\halo.ico"

:shortcut
powershell -NoProfile -ExecutionPolicy Bypass -File "make_shortcut.ps1" -Target "%TARGET%" -Arguments "%ARGS%" -WorkDir "%CD%" -Icon "%ICON%" -Folder Desktop
echo.
choice /c YN /m "Jalankan Halo otomatis saat Windows menyala"
if errorlevel 2 goto done
powershell -NoProfile -ExecutionPolicy Bypass -File "make_shortcut.ps1" -Target "%TARGET%" -Arguments "%ARGS%" -WorkDir "%CD%" -Icon "%ICON%" -Folder Startup
:done
echo.
echo Selesai. Klik dua kali shortcut "Halo" di Desktop untuk menjalankan.
pause
exit /b 0

:nopy
echo Python 3.12 tidak ditemukan. Pasang dari python.org (centang Add python.exe to PATH), lalu jalankan ulang file ini.
pause
exit /b 1

:fail
echo Instalasi dependensi gagal. Salin pesan error di atas dan kirim ke Claude.
pause
exit /b 1
