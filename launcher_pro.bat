@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python protomorph_gui.py
pause
