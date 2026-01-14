@echo off
cd /d "%~dp0"
title Animal Voice Morpher Ultimate
echo Starting Application...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Application Error!
    pause
)
