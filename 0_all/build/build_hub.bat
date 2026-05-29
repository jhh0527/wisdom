@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

for %%I in ("%~dp0..\..") do set "WROOT=%%~fI"

if exist "%~dp0work_hub" rmdir /s /q "%~dp0work_hub"

set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
)
if not defined PYEXE (
  where python >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%I in ('where python') do set "PYEXE=%%I" & goto :have_py
  )
)
:have_py
if not defined PYEXE (
  echo Python을 찾을 수 없습니다.
  exit /b 1
)

echo 사용 중인 Python: "!PYEXE!"
"!PYEXE!" -m pip install -q -r "%~dp0requirements-build.txt"
if errorlevel 1 exit /b 1

echo WisdomHub PyInstaller...
"!PYEXE!" -m PyInstaller --clean --noconfirm --distpath "!WROOT!\all\dist" --workpath "%~dp0work_hub" "%~dp0wisdom_hub.spec"
if errorlevel 1 exit /b 1

echo 완료: "!WROOT!\all\dist\WisdomHub.exe"
exit /b 0
