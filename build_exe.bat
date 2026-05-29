@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYEXE="
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
  if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
)

if "%PYEXE%"=="" (
  echo 로컬에 python.org 설치 폴더가 없습니다: %LocalAppData%\Programs\Python\
  echo PATH의 python을 사용합니다 ^(Microsoft Store 스텁이면 실패할 수 있음^).
  set "PYEXE=python"
)

echo 사용 중인 Python: "%PYEXE%"
"%PYEXE%" --version
if errorlevel 1 (
  echo 위 경로로 Python을 실행할 수 없습니다.
  exit /b 1
)

"%PYEXE%" -c "import sys; assert sys.version_info>=(3,9)" 2>nul
if errorlevel 1 (
  echo Python 3.9 이상이 필요합니다.
  exit /b 1
)

"%PYEXE%" -m pip install -q -r "%~dp0requirements-build.txt"
if errorlevel 1 exit /b 1

"%PYEXE%" -m PyInstaller --onefile --name char_count --console --clean "%~dp0char_count.py"
if errorlevel 1 exit /b 1

echo.
echo 완료: "%~dp0dist\char_count.exe"
exit /b 0
