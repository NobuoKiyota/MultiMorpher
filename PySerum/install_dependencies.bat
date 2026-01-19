@echo off
echo ===========================================
echo Installing Python Dependencies for SFX Suite
echo ===========================================

python -m pip install --upgrade pip

echo.
echo Installing Core Libraries...
pip install numpy scipy librosa soundfile pyworld pandas openpyxl matplotlib Pillow pygame

echo.
echo Installing GUI Libraries...
pip install customtkinter tkinterdnd2

echo.
echo Installing Utils...
pip install packaging odfpy

echo.
echo ===========================================
echo Installation Complete!
echo You can now run the Launcher.
echo ===========================================
pause
