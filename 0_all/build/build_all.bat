@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

for %%I in ("%~dp0..\..") do set "WROOT=%%~fI"

echo [all/build] manuscript_700_splitter 빌드...
call "%WROOT%\1_textTo700Text\build\build_exe.bat"
if errorlevel 1 exit /b 1

echo.
echo [all/build] WisdomHub 빌드...
call "%~dp0build_hub.bat"
if errorlevel 1 exit /b 1

echo.
echo ============================================================
echo   all 빌드 완료
echo   "%WROOT%\1_textTo700Text\dist\manuscript_700_splitter.exe"
echo   "%WROOT%\all\dist\WisdomHub.exe"
echo ============================================================
exit /b 0
