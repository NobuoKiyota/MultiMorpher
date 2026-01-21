@echo off
cd /d "%~dp0"
echo Launching PySerum SFX Generator...

rem Install dependencies
pip install pyaudio numpy customtkinter mido python-rtmidi scipy

python pyserum_main.py

