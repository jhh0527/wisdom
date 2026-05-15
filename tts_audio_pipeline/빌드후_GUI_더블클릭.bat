@echo off
chcp 65001 >nul
cd /d "%~dp0"
title txt2audio — 빌드 후 GUI 실행

echo [1/2] 실행 파일 빌드 ^(PyInstaller^)...
call "%~dp0build\build_exe.bat"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo 빌드 실패 ^(오류 코드 %RC%^). 위 로그를 확인하세요.
  pause
  exit /b %RC%
)

echo.
echo [2/2] GUI 실행...
if not exist "%~dp0dist\txt2audio_gui.exe" (
  echo dist\txt2audio_gui.exe 를 찾을 수 없습니다.
  pause
  exit /b 1
)

start "" "%~dp0dist\txt2audio_gui.exe"
exit /b 0
