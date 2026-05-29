@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM PowerShell에서는 현재 폴더 실행에 .\ 가 필요합니다:  .\run_chatterbox_server.bat
if not exist ".venv_chatterbox\Scripts\python.exe" (
  echo 먼저 setup_chatterbox_venv.ps1 로 .venv_chatterbox 를 만드세요.
  exit /b 1
)
REM 기본: 기업망 SSL 프록시 대응(HF Hub TLS 검증 끔). 집/신뢰망에서 끄려면 다음 줄을 REM 처리하거나 0으로:
set CHATTERBOX_HF_INSECURE_SSL=1

echo Chatterbox HTTP 서버: http://127.0.0.1:8000/tts  (이 창을 닫으면 중지됩니다)
echo HF SSL: CHATTERBOX_HF_INSECURE_SSL=%CHATTERBOX_HF_INSECURE_SSL% ^(0이면 TLS 검증 유지^)
".venv_chatterbox\Scripts\python.exe" run_chatterbox_http_server.py %*
exit /b %ERRORLEVEL%
