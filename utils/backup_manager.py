# utils/backup_manager.py
import os
import pandas as pd
from datetime import datetime
from pathlib import Path
import streamlit as st
from core.db_operations import load_data_db

# Define where backups go
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)

TABLES = [
    "transactions",
    "accounts",
    "budgets",
    "categories",
    "loans",
    "payees",
    "recurring",
    "users",
]

def create_automatic_backup(trigger_name: str) -> str:
    """
    Creates a full Excel backup of the database.
    trigger_name: Reason for backup (e.g., 'pre_reset', 'pre_delete_table')
    Returns: The path of the created backup file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"auto_backup_{trigger_name}_{timestamp}.xlsx"
    filepath = BACKUP_DIR / filename

    try:
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            data_found = False
            for table in TABLES:
                df = load_data_db(table)
                # Save even if empty, to preserve structure, but prefer data
                if df is not None:
                    df.to_excel(writer, sheet_name=table, index=False)
                    if not df.empty:
                        data_found = True
            
        if data_found:
            return str(filepath)
        else:
            # If DB was truly empty, maybe we don't need a backup, 
            # but safer to keep the file just in case.
            return str(filepath)

    except Exception as e:
        st.error(f"⚠️ Automatic Backup Failed: {e}")
        return None