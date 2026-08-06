@echo off
setlocal
cd /d "%~dp0"
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller is required. Install it with: python -m pip install pyinstaller
  exit /b 1
)
python -m PyInstaller --noconfirm --clean release\EmbedPinDoctor.spec
if errorlevel 1 exit /b 1
echo Build complete: dist\EmbedPinDoctor.exe
