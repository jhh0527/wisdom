@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [4_2pngFileName] PyInstaller 빌드 시작...
call "%~dp0build\build_exe.bat"
exit /b %ERRORLEVEL%
