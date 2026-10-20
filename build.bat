@echo off
setlocal
cd /d "%~dp0"
title Halo - Build dan pasang

if not exist "assets\halo.ico" goto noassets
if not exist "assets\halo.png" goto noassets
if not exist "assets\fonts\Inter-Regular.otf" echo PERINGATAN: assets\fonts belum lengkap - Halo akan memakai font cadangan.

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
  --icon "assets\halo.ico" --version-file "version_info.txt" ^
  --add-data "assets;assets" ^
  --hidden-import winrt._winrt ^
  --hidden-import winrt._winrt_windows_foundation ^
  --hidden-import winrt._winrt_windows_foundation_collections ^
  --hidden-import winrt._winrt_windows_storage_streams ^
  --hidden-import winrt._winrt_windows_media_control ^
  --exclude-module tkinter main.py > build.log 2>&1
if errorlevel 1 goto pyfail
if not exist "dist\Halo.exe" goto pyfail
goto pyok

:pyfail
echo.
echo ==== PyInstaller gagal. 25 baris terakhir dari build.log: ====
powershell -NoProfile -Command "Get-Content build.log -Tail 25"
echo ==============================================================
goto fallback

:pyok
set "INSTALL=%LOCALAPPDATA%\Halo"
mkdir "%INSTALL%" 2>nul
copy /y "dist\Halo.exe" "%INSTALL%\Halo.exe" >nul
copy /y "assets\halo.ico" "%INSTALL%\halo.ico" >nul
set "TARGET=%INSTALL%\Halo.exe"
set "ARGS="
set "ICON=%INSTALL%\halo.ico"
goto shortcut

:fallback
echo.
echo MODE CADANGAN: shortcut menjalankan Halo lewat Python (pythonw).
echo Di Task Manager proses ini akan tampil sebagai "Python", bukan "Halo".
echo Kirim isi build.log ke Claude agar penyebabnya bisa diperbaiki.
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
ie4uinit.exe -show >nul 2>nul
echo.
echo Selesai. Klik dua kali shortcut "Halo" di Desktop untuk menjalankan.
pause
exit /b 0

:noassets
echo.
echo Folder assets tidak lengkap. Pastikan ada file berikut di %CD%:
echo   assets\halo.ico
echo   assets\halo.png
echo   assets\fonts\Inter-Regular.otf, Inter-SemiBold.otf, Inter-Bold.otf, Inter-LICENSE.txt
pause
exit /b 1

:nopy
echo Python 3.12 tidak ditemukan. Pasang dari python.org (centang Add python.exe to PATH), lalu jalankan ulang file ini.
pause
exit /b 1

:fail
echo Instalasi dependensi gagal. Salin pesan error di atas dan kirim ke Claude.
pause
exit /b 1
