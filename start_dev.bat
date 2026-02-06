@echo off

REM Set dev schema
set ZIVA_DB_SCHEMA=dev

REM Activate virtual environment
call .venv\Scripts\activate

REM Start Streamlit app
streamlit run main.py

pause

