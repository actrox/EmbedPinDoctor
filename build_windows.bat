@echo off
cd /d "%~dp0"
python -m pip install pyinstaller
python -m PyInstaller --name EmbedPinDoctor --onefile --console start_embedpindoctor.py
pause
