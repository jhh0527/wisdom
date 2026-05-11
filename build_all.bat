@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if /i "%~1"=="nopause" set "NOPAUSE=1"

echo.
echo ============================================================
echo   wisdom — PyInstaller 일괄 빌드 ^(순차 4종^)
echo   char_count + txt2audio + prompt2image + Video Studio
echo ============================================================
echo   개별 패키지만 빌드 시: 해당 하위폴더의 build_exe.bat
echo ------------------------------------------------------------
echo.

set "STEP="

echo [1/4] char_count.exe ...
call "%~dp0build_exe.bat"
if errorlevel 1 set "STEP=char_count"& goto :fail

echo.
echo [2/4] txt2audio.exe ^(CLI^) + txt2audio_gui.exe ...
call "%~dp0tts_audio_pipeline\build_exe.bat"
if errorlevel 1 set "STEP=tts_audio_pipeline (txt2audio)"& goto :fail

echo.
echo [3/4] prompt2image.exe + prompt2image_gui.exe ...
call "%~dp0image_prompt_pipeline\build_exe.bat"
if errorlevel 1 set "STEP=image_prompt_pipeline"& goto :fail

echo.
echo [4/4] VideoStudio.exe ...
call "%~dp0video_studio\build_exe.bat"
if errorlevel 1 set "STEP=video_studio"& goto :fail

echo.
echo ============================================================
echo   전체 빌드 완료
echo ------------------------------------------------------------
echo   "%~dp0dist\char_count.exe"
echo   "%~dp0tts_audio_pipeline\dist\txt2audio.exe"
echo   "%~dp0tts_audio_pipeline\dist\txt2audio_gui.exe"
echo   "%~dp0image_prompt_pipeline\dist\prompt2image.exe"
echo   "%~dp0image_prompt_pipeline\dist\prompt2image_gui.exe"
echo   "%~dp0video_studio\dist\VideoStudio.exe"
echo ============================================================
if not defined NOPAUSE pause
exit /b 0

:fail
echo.
echo [오류] 단계: !STEP!
echo 위 로그를 확인한 뒤, 실패한 하위 폴더의 build_exe.bat 만 다시 실행해도 됩니다.
if not defined NOPAUSE pause
exit /b 1
