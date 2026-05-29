@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%
where py >nul 2>nul && py -3 -m videostudio || python -m videostudio
pause
