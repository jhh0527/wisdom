@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PROOT=%~dp0.."
for %%I in ("%PROOT%") do set "PROOT=%%~fI"

where py >nul 2>nul && (set PY=py -3) || (set PY=python)

echo [1/3] pip install ...
%PY% -m pip install -q -r "%~dp0requirements-build.txt" || exit /b 1

if exist "%~dp0work" rmdir /s /q "%~dp0work"
echo [2/3] PyInstaller ...
%PY% -m PyInstaller --noconfirm --clean --distpath "!PROOT!\dist" --workpath "%~dp0work" "%~dp0video_studio_gui.spec" || exit /b 1

echo [3/3] Done. "!PROOT!\dist\VideoStudio.exe"
exit /b 0
