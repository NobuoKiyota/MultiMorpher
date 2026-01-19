@echo off
setlocal
echo ===========================================
echo Installing Python Dependencies for SFX Suite
echo ===========================================

rem Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not detected!
    echo.
    echo Please install Python (3.10 or newer) from python.org.
    echo IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    echo After installing, please restart this script.
    pause
    exit /b
)

echo Python found. Updating pip...
python -m pip install --upgrade pip

echo.
echo Installing Core Libraries...
python -m pip install numpy scipy librosa soundfile pyworld pandas openpyxl matplotlib Pillow pygame

echo.
echo Installing GUI Libraries...
python -m pip install customtkinter tkinterdnd2

echo.
echo Installing Utils...
python -m pip install packaging odfpy

echo.
echo ===========================================
echo Installation Complete!
echo You can now run the Launcher.
echo ===========================================
pause
