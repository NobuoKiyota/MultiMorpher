@echo off
title MultiMorpher Launcher
echo Starting MultiMorpher...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Error occurred. Installing dependencies...
    pip install -r requirements.txt
    echo.
    echo Retrying launch...
    python main.py
)
pause
