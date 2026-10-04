@echo off
REM ---- Jyotish Agent launcher (Windows) ----
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo No virtual environment found.
    echo Create it first:  py -3.11 -m venv .venv  ^&^&  .venv\Scripts\activate  ^&^&  pip install -r requirements.txt
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo Starting Jyotish Agent at http://localhost:8501 ...
streamlit run app.py
pause
