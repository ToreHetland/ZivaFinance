@echo off

REM 1. Define project path (change drive letter if needed)
set PROJECT_DIR=d:\ziva

REM 2. Move to project directory
cd /d "%PROJECT_DIR%" || (
    echo ❌ Error: Could not find project directory
    pause
    exit /b 1
)

REM 3. Activate virtual environment
IF EXIST ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) ELSE (
    echo ❌ Error: Virtual environment (.venv) not found!
    pause
    exit /b 1
)

REM 4. Launch Streamlit app with auto reload
streamlit run main.py --server.runOnSave true

pause

