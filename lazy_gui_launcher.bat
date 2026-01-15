@echo off
cd /d "%~dp0"
call .venv\Scripts\activate || echo Warning: Could not activate venv, trying global python...
python lazy_gui.py
pause
