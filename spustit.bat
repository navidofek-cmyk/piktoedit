@echo off
rem Spusteni editoru piktogramu.
cd /d "%~dp0"
python main.py %*
if errorlevel 1 pause
