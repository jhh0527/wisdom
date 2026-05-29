@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv_chatterbox\Scripts\python.exe" (
  echo .venv_chatterbox 가 없습니다. setup_chatterbox_venv.ps1 을 먼저 실행하세요.
  pause
  exit /b 1
)
echo Chatterbox 로컬 설치용 GUI 실행…
".venv_chatterbox\Scripts\python.exe" -m txt2audio --gui
exit /b %ERRORLEVEL%
