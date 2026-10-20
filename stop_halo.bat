@echo off
rem Menghentikan Halo, baik versi Halo.exe maupun versi pythonw (shortcut cadangan).
taskkill /f /im Halo.exe >nul 2>nul
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'Halo' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Halo dihentikan.
timeout /t 2 >nul
