@echo off
cd /d "%~dp0"
echo Installing dependencies...
pip install customtkinter librosa numpy soundfile scipy pyworld tkinterdnd2
echo Starting Lazy GUI...
python lazy_gui.py
pause
