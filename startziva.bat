@echo off
:: Move to the directory where this script is located
cd /d %~dp0
echo --- Ziva Financial Launcher for Windows ---

:: 1. Check if the Windows Virtual Environment exists
IF NOT EXIST ".venv_win" (
    echo [!] Windows environment not found. Creating it now...
    python -m venv .venv_win
    echo [!] Installing required libraries...
    call .venv_win\Scripts\activate
    pip install -r requirements.txt
    pip install plotly google-genai
    echo [!] Setup complete.
) ELSE (
    echo [!] Windows environment found. Activating...
    call .venv_win\Scripts\activate
)

:: 2. Launch the app
echo [!] Starting Ziva...
streamlit run main.py

pause