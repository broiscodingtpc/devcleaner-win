@echo off
REM Dev mode: runs inline (no UAC), useful for debugging.
setlocal
pushd "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)
call ".venv\Scripts\activate.bat"
pip install --upgrade pip >nul
pip install -r requirements.txt
python main.py
popd
endlocal
