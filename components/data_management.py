# components/data_management.py
import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime
from core.db_operations import load_data_db, save_data_db, execute_query_db

# Tables that depend on specific IDs (Foreign Keys)
# We MUST preserve IDs for these to keep links working.
LINKED_TABLES = ["loans", "loan_extra_payments", "loan_terms_history"]

# Schema definition for cleaning
SCHEMA_COLUMNS = {
    "transactions": ["id", "date", "type", "account", "category", "payee", "amount", "description", "user_id"],
    "accounts": ["id", "name", "account_type", "balance", "currency", "is_default", "credit_interest_rate", "credit_due_day", "credit_source_account", "credit_period_mode", "credit_start_day", "credit_end_day", "description", "created_date", "last_updated", "user_id"],
    "loans": ["id", "name", "balance", "interest_rate", "min_payment", "user_id", "admin_fee", "payment_day", "pay_from_account", "start_date", "term_years", "target_date", "calculation_mode", "interest_only_from", "interest_only_to", "created_at", "loan_type"],
    "categories": ["id", "name", "type", "parent_category", "user_id"],
    "payees": ["id", "name", "user_id"],
    "budgets": ["id", "month", "category", "budget_amount", "user_id"],
    "recurring": ["id", "type", "account", "category", "payee", "amount", "description", "start_date", "frequency", "interval", "last_generated_date", "user_id"],
    "loan_extra_payments": ["id", "loan_id", "pay_date", "amount", "note", "user_id", "created_at"],
    "loan_terms_history": ["id", "loan_id", "change_date", "interest_rate", "admin_fee", "note", "user_id", "created_at"]
}

INTEGER_COLUMNS = ["id", "payment_day", "term_years", "credit_due_day", "credit_start_day", "credit_end_day", "interval", "loan_id", "smtp_port"]
USER_DATA_TABLES = list(SCHEMA_COLUMNS.keys())

def _get_user_id():
    return st.session_state.get("username", "default")

def render_data_management():
    st.header("💾 Data Management")
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Manage Transactions", "📤 Export Data", "📥 Import Data", "🗑️ Data Cleanup"])
    with tab1: render_transaction_editor()
    with tab2: render_export_section()
    with tab3: render_import_section()
    with tab4: render_cleanup_section()

def _clean_records_for_db(df, table_name, user_id):
    """
    Cleans DataFrame and converts to list of dicts.
    - Drops 'id' for non-linked tables (fixes UniqueViolation).
    - Keeps 'id' for linked tables (loans).
    - Replaces NaN/NaT with None.
    """
    # 1. Filter Columns
    allowed_cols = SCHEMA_COLUMNS.get(table_name, [])
    if allowed_cols:
        valid_cols = [c for c in df.columns if c in allowed_cols]
        df = df[valid_cols]
    
    # 2. Convert Dates
    for col in df.columns:
        if "date" in col or "created_at" in col or "last_updated" in col:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # 3. Process Records
    records = df.to_dict(orient="records")
    cleaned_records = []

    for rec in records:
        clean_rec = {}
        for k, v in rec.items():
            # Force User ID
            if k == "user_id":
                clean_rec[k] = user_id
                continue
            
            # DROP ID if not a linked table (Allow DB to auto-increment)
            if k == "id" and table_name not in LINKED_TABLES:
                continue 
            
            # Handle Nulls
            if pd.isna(v) or v is pd.NaT:
                clean_rec[k] = None
                continue
            
            # Handle Integers
            if k in INTEGER_COLUMNS:
                try: clean_rec[k] = int(float(v))
                except: clean_rec[k] = None
            else:
                clean_rec[k] = v
        
        if "user_id" in allowed_cols:
            clean_rec["user_id"] = user_id
            
        cleaned_records.append(clean_rec)

    return cleaned_records

def render_transaction_editor():
    st.subheader("📝 Edit or Delete Transactions")
    user_id = _get_user_id()
    df = load_data_db("transactions", user_id=user_id)
    
    if df is None or df.empty:
        st.warning("No transactions found.")
        return

    col1, col2 = st.columns([2, 1])
    with col1: search_term = st.text_input("🔍 Search", placeholder="Payee, Category...")
    with col2: show_all = st.checkbox("Show all history", value=False)
    
    if "date" in df.columns: df["date"] = pd.to_datetime(df["date"], errors="coerce")
    
    mask = pd.Series([True] * len(df))
    if not show_all:
        cutoff = pd.Timestamp.today() - pd.Timedelta(days=60)
        mask &= (df["date"] >= cutoff)
    
    if search_term:
        t = search_term.lower()
        mask &= (df["payee"].astype(str).str.lower().str.contains(t) | 
                 df["category"].astype(str).str.lower().str.contains(t) | 
                 df["amount"].astype(str).str.contains(t))
    
    filtered_df = df[mask].sort_values(by="date", ascending=False).reset_index(drop=True)

    edited_df = st.data_editor(
        filtered_df, num_rows="dynamic", key="tx_editor", width="stretch",
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "date": st.column_config.DateColumn("Date", format="DD.MM.YYYY"),
            "type": st.column_config.SelectboxColumn("Type", options=["Expense", "Income", "Transfer"]),
            "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
        },
        hide_index=True
    )

    if st.button("💾 Save Changes", type="primary"):
        try:
            # Detect deletions
            orig_ids = set(filtered_df["id"].dropna().unique())
            new_ids = set(edited_df["id"].dropna().unique())
            to_delete = orig_ids - new_ids
            
            if to_delete:
                for d_id in to_delete:
                    execute_query_db("DELETE FROM transactions WHERE id = :id AND user_id = :uid", {"id": d_id, "uid": user_id})

            # Save updates (using ID to update existing)
            # For transaction editor, we DO keep ID to update rows instead of duplicate
            # The _clean_records function usually drops ID, but here we can manually handle it
            # Or just rely on save_data_db's update logic if ID is present.
            
            # Let's use a simpler path for the Editor than the Import
            # Just convert and save
            records = edited_df.to_dict(orient="records")
            success = 0
            for r in records:
                # Sanitize
                for k,v in r.items():
                    if pd.isna(v): r[k] = None
                r["user_id"] = user_id
                
                if save_data_db("transactions", r): success += 1
            
            st.success(f"✅ Saved {success} changes!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

def render_export_section():
    st.subheader("📤 Export Your Data")
    user_id = _get_user_id()
    if st.button("🚀 Generate Backup (Excel)"):
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                for table in USER_DATA_TABLES:
                    df = load_data_db(table, user_id=user_id)
                    if df is not None and not df.empty:
                        for c in df.columns:
                            if pd.api.types.is_datetime64_any_dtype(df[c]):
                                try: df[c] = df[c].dt.tz_localize(None)
                                except: pass
                        df.to_excel(writer, sheet_name=table, index=False)
                    else:
                        pd.DataFrame().to_excel(writer, sheet_name=table, index=False)
            
            st.download_button("📥 Download", buffer.getvalue(), f"backup_{datetime.now().strftime('%Y%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.success("Done!")
        except Exception as e: st.error(f"Export failed: {e}")

def render_import_section():
    st.subheader("📥 Import & Restore Data")
    user_id = _get_user_id()
    st.warning(f"⚠️ This replaces data for **{user_id}**.")
    
    f = st.file_uploader("Backup File (.xlsx)", type=["xlsx"])
    if f and st.button("🔄 Restore"):
        success = 0
        try:
            xls = pd.ExcelFile(f)
            for sheet in xls.sheet_names:
                if sheet in USER_DATA_TABLES:
                    try:
                        df = pd.read_excel(xls, sheet_name=sheet)
                        if df.empty: continue
                        
                        # CLEAN & PREPARE
                        # This strips IDs for standard tables (fixing UniqueViolation)
                        records = _clean_records_for_db(df, sheet, user_id)
                        if not records: continue

                        # DELETE OLD DATA
                        # For linked tables (loans), we must be careful. 
                        # But for a full restore, wiping by user_id is standard.
                        execute_query_db(f"DELETE FROM {sheet} WHERE user_id = :uid", {"uid": user_id})
                        
                        # INSERT NEW
                        from core.db_operations import add_record_db
                        add_record_db(sheet, records)
                        success += 1
                    except Exception as ex:
                        st.error(f"❌ {sheet}: {ex}")
            
            if success > 0: st.success(f"✅ Restored {success} tables!")
        except Exception as e: st.error(f"Import Error: {e}")

def render_cleanup_section():
    st.subheader("🗑️ Data Cleanup")
    user_id = _get_user_id()
    if st.button("🔍 Remove Duplicates"):
        df = load_data_db("transactions", user_id=user_id)
        if df is not None and not df.empty:
            start = len(df)
            clean = df.drop_duplicates(subset=["date", "account", "category", "payee", "amount"])
            if start - len(clean) > 0:
                execute_query_db("DELETE FROM transactions WHERE user_id = :uid", {"uid": user_id})
                recs = _clean_records_for_db(clean, "transactions", user_id)
                # For cleanup, we want to KEEP existing IDs if possible, but simpler to regenerate
                # safely to avoid conflicts.
                from core.db_operations import add_record_db
                add_record_db("transactions", recs)
                st.success(f"Removed {start - len(clean)} duplicates.")
                st.rerun()
            else: st.info("No duplicates.")
    
    st.divider()
    table = st.selectbox("Clear Table", [""] + USER_DATA_TABLES)
    if table and st.button(f"💥 Clear {table}"):
        execute_query_db(f"DELETE FROM {table} WHERE user_id = :uid", {"uid": user_id})
        st.success("Cleared.")
        st.rerun()