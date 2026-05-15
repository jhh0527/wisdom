@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PROOT=%~dp0.."
for %%I in ("%PROOT%") do set "PROOT=%%~fI"

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
  echo - py -3 ^(Python Launcher^) 또는 PATH의 python 또는
  echo   %LocalAppData%\Programs\Python\Python3* 설치를 확인하세요.
  exit /b 1
)

echo 사용 중인 Python: "!PYEXE!"
"!PYEXE!" --version
if errorlevel 1 (
  echo 위 경로로 Python을 실행할 수 없습니다.
  exit /b 1
)

"!PYEXE!" -c "import sys; assert sys.version_info>=(3,9)" 2>nul
if errorlevel 1 (
  echo Python 3.9 이상이 필요합니다.
  exit /b 1
)

echo 런타임 의존성 설치...
"!PYEXE!" -m pip install -q -r "!PROOT!\requirements.txt"
if errorlevel 1 exit /b 1

echo 빌드 도구 설치...
"!PYEXE!" -m pip install -q -r "%~dp0requirements-build.txt"
if errorlevel 1 exit /b 1

if exist "%~dp0work" rmdir /s /q "%~dp0work"
echo PyInstaller 실행 ^(CLI: "!PROOT!\dist\txt2audio.exe"^)...
"!PYEXE!" -m PyInstaller --clean --noconfirm --distpath "!PROOT!\dist" --workpath "%~dp0work" "%~dp0txt2audio.spec"
if errorlevel 1 exit /b 1

if exist "%~dp0work" rmdir /s /q "%~dp0work"
echo PyInstaller 실행 ^(GUI: "!PROOT!\dist\txt2audio_gui.exe"^)...
"!PYEXE!" -m PyInstaller --clean --noconfirm --distpath "!PROOT!\dist" --workpath "%~dp0work" "%~dp0txt2audio_gui.spec"
if errorlevel 1 exit /b 1

echo.
echo 완료:
echo   CLI  "!PROOT!\dist\txt2audio.exe"
echo   GUI  "!PROOT!\dist\txt2audio_gui.exe"  ^(더블클릭 — 파일 선택^)
echo 사용 예: txt2audio.exe -i 대본.txt -o 음성.mp3
exit /b 0
