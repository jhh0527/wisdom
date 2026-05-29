@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if /i "%~1"=="nopause" set "NOPAUSE=1"

echo.
echo ============================================================
echo   wisdom — PyInstaller 일괄 빌드 ^(순차 6종^)
echo   char_count + txt2audio + prompt2image + Video Studio + manuscript + WisdomHub
echo ============================================================
echo   개별 패키지만 빌드 시: 해당 하위폴더\build\build_exe.bat
echo ------------------------------------------------------------
echo.

set "STEP="

echo [1/4] char_count.exe ...
call "%~dp0build_exe.bat"
if errorlevel 1 set "STEP=char_count"& goto :fail

echo.
echo [2/4] txt2audio.exe ^(CLI^) + txt2audio_gui.exe ...
call "%~dp0tts_audio_pipeline\build\build_exe.bat"
if errorlevel 1 set "STEP=tts_audio_pipeline (txt2audio)"& goto :fail

echo.
echo [3/4] 4_srtToImage.exe + 4_srtToImage_gui.exe ...
call "%~dp04_srtToImage\build\build_exe.bat"
if errorlevel 1 set "STEP=4_srtToImage"& goto :fail

echo.
echo [4/6] VideoStudio.exe ...
call "%~dp0video_studio\build\build_exe.bat"
if errorlevel 1 set "STEP=video_studio"& goto :fail

echo.
echo [5/6] manuscript_700_splitter.exe ...
call "%~dp01_textTo700Text\build\build_exe.bat"
if errorlevel 1 set "STEP=1_textTo700Text"& goto :fail

echo.
echo [6/6] WisdomHub.exe ^(all/dist, 탭 런처^) ...
call "%~dp0all\build\build_hub.bat"
if errorlevel 1 set "STEP=all WisdomHub"& goto :fail

echo.
echo ============================================================
echo   전체 빌드 완료
echo ------------------------------------------------------------
echo   "%~dp0dist\char_count.exe"
echo   "%~dp0tts_audio_pipeline\dist\txt2audio.exe"
echo   "%~dp0tts_audio_pipeline\dist\txt2audio_gui.exe"
echo   "%~dp04_srtToImage\dist\4_srtToImage.exe"
echo   "%~dp04_srtToImage\dist\4_srtToImage_gui.exe"
echo   "%~dp0video_studio\dist\VideoStudio.exe"
echo   "%~dp01_textTo700Text\dist\manuscript_700_splitter.exe"
echo   "%~dp0all\dist\WisdomHub.exe"
echo ============================================================
if not defined NOPAUSE pause
exit /b 0

:fail
echo.
echo [오류] 단계: !STEP!
echo 위 로그를 확인한 뒤, 실패한 하위 폴더의 build\build_exe.bat 만 다시 실행해도 됩니다.
if not defined NOPAUSE pause
exit /b 1
