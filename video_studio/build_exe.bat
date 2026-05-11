@echo off
cd /d "%~dp0"
set PYTHONUTF8=1

where py >nul 2>nul && (set PY=py -3) || (set PY=python)

echo [1/3] pip install ...
%PY% -m pip install -q -r requirements-build.txt || exit /b 1

echo [2/3] PyInstaller ...
%PY% -m PyInstaller --noconfirm --clean video_studio_gui.spec || exit /b 1

echo [3/3] Done. dist\VideoStudio.exe
exit /b 0
