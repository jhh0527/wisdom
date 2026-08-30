@echo off
setlocal
cd /d "%~dp0.."
echo [wuxia 허브] PyInstaller 빌드 시작...
taskkill /IM wuxia_hub_gui.exe /F 2>nul
python -m pip install -q pyinstaller 2>nul
python -m pip install -q windnd 2>nul
python -m playwright install chrome 2>nul
python -m PyInstaller --noconfirm --clean "%~dp0wuxia_hub_gui.spec"
if errorlevel 1 exit /b 1
echo.
echo 완료: "%cd%\dist\wuxia_hub_gui.exe"
endlocal
