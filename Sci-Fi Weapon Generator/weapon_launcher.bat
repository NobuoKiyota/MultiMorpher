@echo off
cd /d "%~dp0"
echo Launching Sci-Fi Weapon Generator...

rem Check if venv exists (assuming potentially shared or local)
rem Just run with local python for now as per user environment
rem Install sounddevice just in case (fast check)
pip install sounddevice soundfile numpy scipy customtkinter

python weapon_gui.py
pause
