@echo off
setlocal
echo ===========================================
echo SFX Suite Dependency Installer
echo ===========================================

rem 1. Python command check
echo Checking for Python...
set PYTHON_CMD=python

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo 'python' command not found. Checking for 'py' launcher...
    where py >nul 2>&1
    if %errorlevel% neq 0 (
        goto :PYTHON_NOT_FOUND
    ) else (
        set PYTHON_CMD=py
    )
)

echo Using Python command: %PYTHON_CMD%
%PYTHON_CMD% --version
if %errorlevel% neq 0 (
    echo [WARNING] Python command exists but failed to return version.
    goto :PYTHON_NOT_FOUND
)

echo.
echo ===========================================
echo Installing Libraries...
echo ===========================================

rem Upgrade PIP
echo [1/4] Upgrading pip...
%PYTHON_CMD% -m pip install --upgrade pip
if %errorlevel% neq 0 goto :ERROR

rem Core
echo.
echo [2/4] Installing Core Libraries (numpy, scipy, librosa...)...
%PYTHON_CMD% -m pip install numpy scipy librosa soundfile pyworld pandas openpyxl matplotlib Pillow pygame
if %errorlevel% neq 0 goto :ERROR

rem GUI
echo.
echo [3/4] Installing GUI Libraries (customtkinter...)...
%PYTHON_CMD% -m pip install customtkinter tkinterdnd2
if %errorlevel% neq 0 goto :ERROR

rem Utils
echo.
echo [4/4] Installing Utils...
%PYTHON_CMD% -m pip install packaging odfpy
if %errorlevel% neq 0 goto :ERROR

echo.
echo ===========================================
echo Installation SUCCESS!
echo You can now run the Launcher.
echo ===========================================
pause
exit /b 0

:PYTHON_NOT_FOUND
echo.
echo [ERROR] Python not found or not working correctly.
echo.
echo Current Status:
echo 'python' command: Not recognized or silent
echo 'py' launcher   : Not recognized
echo.
echo ========================================================
echo PLEASE INSTALL PYTHON:
echo 1. Go to https://www.python.org/downloads/
echo 2. Download Python 3.10, 3.11, or 3.12
echo 3. Run Installer
echo 4. [IMPORTANT] Check "Add Python to PATH" at the bottom!
echo ========================================================
echo.
pause
exit /b 1

:ERROR
echo.
echo [ERROR] Installation failed during pip install.
echo Please check your internet connection or try running as Admin.
echo.
pause
exit /b 1
