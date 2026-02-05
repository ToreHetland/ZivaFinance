# components/data_management.py
import streamlit as st
import pandas as pd
import io
from datetime import datetime
from core.db_operations import load_data_db, save_data_db, execute_query_db, sanitize_for_db

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
from config.i18n import t

def render_data_management():
    """Render the data management dashboard to interact with the database."""
    st.header("💾 Data Management")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📝 Manage Transactions", "📤 Export Data", "📥 Import Data", "🗑️ Data Cleanup"]
    )

    with tab1:
        render_transaction_editor()
    with tab2:
        render_export_section()
    with tab3:
        render_import_section()
    with tab4:
        render_cleanup_section()

def render_transaction_editor():
    st.subheader("📝 Edit or Delete Transactions")
    st.info("💡 Tip: Use the search box to find the transaction, edit it in the grid, and click 'Save Changes'.")

    # 1. Load Data
    df = load_data_db("transactions")
    if df.empty:
        st.warning("No transactions found.")
        return

    # 2. Search Filters
    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input("🔍 Search (Payee, Category, Amount)", placeholder="e.g. Ikea...")
    with col2:
        show_all = st.checkbox("Show all history", value=False)
    
    # Apply Filters
    # Safe date conversion with warning suppression
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    
    mask = pd.Series([True] * len(df))
    if not show_all:
        cutoff = pd.Timestamp.today() - pd.Timedelta(days=60)
        mask &= (df["date"] >= cutoff)
    
    if search_term:
        term = search_term.lower()
        mask &= (
            df["payee"].astype(str).str.lower().str.contains(term) |
            df["category"].astype(str).str.lower().str.contains(term) |
            df["amount"].astype(str).str.contains(term)
        )
    
    filtered_df = df[mask].sort_values(by="date", ascending=False).reset_index(drop=True)

    # 3. The Editor
    # FIX: Replaced deprecated use_container_width with width="stretch" (implicit for st.data_editor defaults)
    edited_df = st.data_editor(
        filtered_df,
        num_rows="dynamic",
        key="tx_manager_editor",
        use_container_width=True, # Keeping this for now as 'width="stretch"' is for st.dataframe, data_editor supports use_container_width until full removal
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "date": st.column_config.DateColumn("Date", format="DD.MM.YYYY"),
            "type": st.column_config.SelectboxColumn("Type", options=["Expense", "Income", "Transfer"]),
            "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
            "account": st.column_config.TextColumn("Account"),
            "category": st.column_config.TextColumn("Category"),
            "payee": st.column_config.TextColumn("Payee"),
            "description": st.column_config.TextColumn("Notes"),
        },
        hide_index=True
    )

    # 4. Save Logic
    if st.button("💾 Save Changes", type="primary"):
        try:
            current_full_db = load_data_db("transactions")
            
            # Ensure dates are datetime objects in the full DB for consistent matching/updating
            if "date" in current_full_db.columns:
                current_full_db["date"] = pd.to_datetime(current_full_db["date"], dayfirst=True, errors="coerce")

            original_ids_in_view = set(filtered_df["id"].dropna().unique())
            new_ids_in_view = set(edited_df["id"].dropna().unique())
            
            # Find Deletions
            ids_to_delete = original_ids_in_view - new_ids_in_view
            
            if ids_to_delete:
                placeholders = ",".join("?" * len(ids_to_delete))
                execute_query_db(f"DELETE FROM transactions WHERE id IN ({placeholders})", tuple(ids_to_delete))
                st.toast(f"🗑️ Deleted {len(ids_to_delete)} transaction(s).")

            # Apply Updates
            updated_full_db = current_full_db.copy()
            # Remove deleted rows from memory df
            updated_full_db = updated_full_db[~updated_full_db["id"].isin(ids_to_delete)] 
            
            updated_full_db.set_index("id", inplace=True)
            edited_df_indexed = edited_df.set_index("id")
            
            # Update only the rows that exist in both
            updated_full_db.update(edited_df_indexed)
            updated_full_db.reset_index(inplace=True)
            
            # Force sanitization before saving
            final_df = sanitize_for_db(updated_full_db)
            
            # Corrected argument order: Table Name FIRST
            if save_data_db("transactions", final_df, if_exists="replace"):
                st.success("✅ Changes saved successfully!")
                st.rerun()
            else:
                st.error("Failed to save changes to database.")
            
        except Exception as e:
            st.error(f"Error saving changes: {e}")

def render_export_section():
    st.subheader("📤 Export Your Data")
    st.write("Create a complete backup of all your data.")

    if st.button("🚀 Generate Full Backup (Excel)", key="export_btn"):
        try:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                for table in TABLES:
                    df = load_data_db(table)
                    df.to_excel(writer, sheet_name=table, index=False)

            excel_data = excel_buffer.getvalue()
            filename = f"finance_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

            st.download_button(
                label="📥 Download Backup File",
                data=excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            st.success("Backup file generated successfully!")

        except Exception as e:
            st.error(f"Error during export: {str(e)}")

def render_import_section():
    st.subheader("📥 Import & Restore Data")
    st.warning("⚠️ This will **REPLACE** all existing data in your database.")

    uploaded_file = st.file_uploader("Choose a backup (.xlsx) file", type=["xlsx"])

    if uploaded_file is not None:
        if st.button("🔄 Restore From Backup", key="import_btn"):
            try:
                success_count = 0
                with st.spinner("Restoring data..."):
                    xls = pd.ExcelFile(uploaded_file)
                    for sheet_name in xls.sheet_names:
                        if sheet_name in TABLES:
                            df = pd.read_excel(xls, sheet_name=sheet_name)
                            
                            if sheet_name == "transactions" and "date" in df.columns:
                                df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
                            
                            # Sanitize here to catch any timestamps before saving
                            clean_df = sanitize_for_db(df)
                            
                            # Corrected argument order: Table Name FIRST
                            if save_data_db(sheet_name, clean_df, if_exists="replace"):
                                success_count += 1
                            else:
                                st.error(f"Failed to restore table: {sheet_name}")
                
                if success_count > 0:
                    st.success(f"✅ Data restored successfully ({success_count} tables)! Please refresh the page.")
                else:
                    st.error("No data was restored. Please check the logs.")
                
            except Exception as e:
                st.error(f"Error during import: {str(e)}")

def render_cleanup_section():
    st.subheader("🗑️ Data Cleanup")
    st.warning("⚠️ These actions are irreversible.")

    if st.button("🔍 Find & Remove Duplicates", key="find_duplicates_btn"):
        transactions_df = load_data_db("transactions")
        if not transactions_df.empty:
            rows_before = len(transactions_df)
            clean_df = transactions_df.drop_duplicates(
                subset=["date", "account", "category", "payee", "amount"]
            )
            rows_after = len(clean_df)
            duplicates_found = rows_before - rows_after

            if duplicates_found > 0:
                # Corrected argument order: Table Name FIRST
                save_data_db("transactions", clean_df, if_exists="replace")
                st.success(f"Removed {duplicates_found} duplicate transactions.")
                st.rerun()
            else:
                st.info("No duplicate transactions found.")

    st.divider()

    table_to_clear = st.selectbox("Select table to clear", options=[""] + TABLES)

    if table_to_clear:
        confirmation = st.text_input(f"Type **DELETE {table_to_clear.upper()}** to confirm")
        if st.button(
            f"💥 Clear {table_to_clear} Table",
            disabled=(confirmation != f"DELETE {table_to_clear.upper()}"),
        ):
            execute_query_db(f"DELETE FROM {table_to_clear}")
            st.success(f"All data from '{table_to_clear}' has been cleared.")
            st.rerun()