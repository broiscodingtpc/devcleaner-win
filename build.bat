@echo off
setlocal
pushd "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
)
call ".venv\Scripts\activate.bat"

pip install --upgrade pip >nul
pip install -r requirements.txt
pip install pyinstaller

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

pyinstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name WinCleaner ^
    --uac-admin ^
    --collect-all customtkinter ^
    --hidden-import send2trash ^
    --hidden-import psutil ^
    main.py

if errorlevel 1 (
    echo [ERROR] PyInstaller failed.
    popd
    exit /b 1
)

echo.
echo [OK] Build complete: dist\WinCleaner.exe
popd
endlocal
