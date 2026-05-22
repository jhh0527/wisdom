@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PROOT=%~dp0.."
for %%I in ("%PROOT%") do set "PROOT=%%~fI"

echo [1/5] 이전 PyInstaller 작업 폴더 제거...
if exist "%~dp0work" rmdir /s /q "%~dp0work"
if exist "%~dp0elsub_gui" rmdir /s /q "%~dp0elsub_gui"

set "PYEXE="

where py >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
)

if not defined PYEXE (
  where python >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%I in ('where python') do (
      set "PYEXE=%%I"
      goto :have_python
    )
  )
)

:have_python
if not defined PYEXE (
  for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
      set "PYEXE=%%D\python.exe"
      goto :done_scan
    )
  )
)
:done_scan

if not defined PYEXE (
  echo Python을 찾을 수 없습니다.
  pause
  exit /b 1
)

echo 사용 중인 Python: "!PYEXE!"
"!PYEXE!" -c "import sys; assert sys.version_info>=(3,9)" 2>nul
if errorlevel 1 (
  echo Python 3.9 이상이 필요합니다.
  pause
  exit /b 1
)

echo [2/5] 빌드 도구 설치...
"!PYEXE!" -m pip install -q -r "%~dp0requirements-build.txt"
if errorlevel 1 (
  echo 빌드 도구 설치 실패.
  pause
  exit /b 1
)

echo [3/5] 실행 중인 3_ttsToVoice_gui 종료 및 기존 exe 잠금 해제...
taskkill /F /IM 3_ttsToVoice_gui.exe >nul 2>&1
ping -n 2 127.0.0.1 >nul
set "DISTEXE=!PROOT!\dist\3_ttsToVoice_gui.exe"
if exist "!DISTEXE!" (
  del /F /Q "!DISTEXE!" >nul 2>&1
)
if exist "!DISTEXE!" (
  move /Y "!DISTEXE!" "!DISTEXE!.old" >nul 2>&1
  del /F /Q "!DISTEXE!.old" >nul 2>&1
)
if exist "!DISTEXE!" (
  echo.
  echo dist\3_ttsToVoice_gui.exe 를 덮어쓸 수 없습니다.
  echo   - 작업 관리자에서 3_ttsToVoice_gui 를 모두 종료한 뒤 다시 빌드하세요.
  echo   - 탐색기 미리보기/백신이 파일을 잡고 있을 수도 있습니다.
  pause
  exit /b 1
)

echo [4/5] PyInstaller 실행 (GUI: "!PROOT!\dist\3_ttsToVoice_gui.exe")...
"!PYEXE!" -m PyInstaller --clean --noconfirm --distpath "!PROOT!\dist" --workpath "%~dp0work" "%~dp0elsub_gui.spec"
if errorlevel 1 (
  echo PyInstaller 실행 실패.
  pause
  exit /b 1
)

if not exist "!PROOT!\dist\3_ttsToVoice_gui.exe" (
  echo dist\3_ttsToVoice_gui.exe 를 찾을 수 없습니다.
  pause
  exit /b 1
)

if exist "!PROOT!\elsub_config.json" (
  copy /Y "!PROOT!\elsub_config.json" "!PROOT!\dist\elsub_config.json" >nul
  echo  - 설정 복사: elsub_config.json -^> dist\
) else if exist "!PROOT!\elsub_config.json.bk" (
  copy /Y "!PROOT!\elsub_config.json.bk" "!PROOT!\dist\elsub_config.json" >nul
  echo  - 설정 복사: elsub_config.json.bk -^> dist\elsub_config.json
) else (
  echo  - 경고: elsub_config.json 이 없습니다. dist\ 아래에 직접 만들어 두세요.
)

echo [5/5] GUI 실행: "!PROOT!\dist\3_ttsToVoice_gui.exe"
start "" "!PROOT!\dist\3_ttsToVoice_gui.exe"

exit /b 0
