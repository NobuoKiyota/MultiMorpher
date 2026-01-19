@echo off
rem SFX Launcher Shortcut
rem This script runs the sfx_launcher_app.py located in the same directory (PySerum).
rem You can create a shortcut to this file and place it on your Desktop.

cd /d %~dp0
start "" pythonw sfx_launcher_app.py
exit
