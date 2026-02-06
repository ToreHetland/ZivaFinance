# components/data_management.py
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import streamlit as st

from core.db_operations import load_data_db, execute_query_db

# Optional helper: don't crash if missing
try:
    from core.db_operations import save_data_db
except ImportError:
    def save_data_db(*args, **kwargs):
        return False

try:
    from core.db_operations import add_record_db
except ImportError:
    add_record_db = None


# Tables that depend on specific IDs (Foreign Keys)
# We MUST preserve IDs for these to keep links working.
LINKED_TABLES = ["loans", "loan_extra_payments", "loan_terms_history"]

# Schema definition for cleaning
SCHEMA_COLUMNS: Dict[str, List[str]] = {
    "transactions": ["id", "date", "type", "account", "category", "payee", "amount", "description", "user_id"],
    "accounts": [
        "id", "name", "account_type", "balance", "currency", "is_default",
        "credit_interest_rate", "credit_due_day", "credit_source_account",
        "credit_period_mode", "credit_start_day", "credit_end_day",
        "description", "created_date", "last_updated", "user_id"
    ],
    "loans": [
        "id", "name", "balance", "interest_rate", "min_payment", "user_id",
        "admin_fee", "payment_day", "pay_from_account", "start_date",
        "term_years", "target_date", "calculation_mode",
        "interest_only_from", "interest_only_to", "created_at", "loan_type"
    ],
    "categories": ["id", "name", "type", "parent_category", "user_id"],
    "payees": ["id", "name", "user_id"],
    "budgets": ["id", "month", "category", "budget_amount", "user_id"],
    "recurring": [
        "id", "type", "account", "category", "payee", "amount",
        "description", "start_date", "frequency", "interval",
        "last_generated_date", "user_id"
    ],
    "loan_extra_payments": ["id", "loan_id", "pay_date", "amount", "note", "user_id", "created_at"],
    "loan_terms_history": ["id", "loan_id", "change_date", "interest_rate", "admin_fee", "note", "user_id", "created_at"],
}

INTEGER_COLUMNS = [
    "id", "payment_day", "term_years", "credit_due_day", "credit_start_day",
    "credit_end_day", "interval", "loan_id", "smtp_port"
]

USER_DATA_TABLES = list(SCHEMA_COLUMNS.keys())


def _get_user_id() -> str:
    return st.session_state.get("username", "default")


def render_data_management():
    st.header("💾 Data Management")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 Manage Transactions",
        "📤 Export Data",
        "📥 Import Data",
        "🗑️ Data Cleanup",
    ])

    with tab1:
        render_transaction_editor()
    with tab2:
        render_export_section()
    with tab3:
        render_import_section()
    with tab4:
        render_cleanup_section()


def _coerce_datetime_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Convert columns that look like dates into datetime (NaT on errors)."""
    for col in df.columns:
        c = col.lower()
        if "date" in c or c in ("created_at", "last_updated"):
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _clean_records_for_db(df: pd.DataFrame, table_name: str, user_id: str) -> List[Dict[str, Any]]:
    """
    Cleans DataFrame and converts to list of dicts.
    - Drops 'id' for non-linked tables (fixes UniqueViolation).
    - Keeps 'id' for linked tables (loans/loan history) so FK links remain stable.
    - Replaces NaN/NaT with None.
    - Forces user_id.
    """
    df = df.copy()

    # 1) Filter Columns (whitelist)
    allowed_cols = SCHEMA_COLUMNS.get(table_name, [])
    if allowed_cols:
        df = df[[c for c in df.columns if c in allowed_cols]]

    # 2) Coerce date-ish columns
    df = _coerce_datetime_cols(df)

    # 3) Convert to records + clean
    records = df.to_dict(orient="records")
    cleaned_records: List[Dict[str, Any]] = []

    for rec in records:
        clean_rec: Dict[str, Any] = {}
        for k, v in rec.items():
            # Force User ID
            if k == "user_id":
                clean_rec[k] = user_id
                continue

            # Drop ID if not a linked table
            if k == "id" and table_name not in LINKED_TABLES:
                continue

            # Null handling
            if v is pd.NaT or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
                clean_rec[k] = None
                continue

            # Integers
            if k in INTEGER_COLUMNS:
                try:
                    clean_rec[k] = int(float(v))
                except Exception:
                    clean_rec[k] = None
            else:
                clean_rec[k] = v

        # Ensure user_id exists if part of schema
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

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input("🔍 Search", placeholder="Payee, Category, Amount…")
    with col2:
        show_all = st.checkbox("Show all history", value=False)

    mask = pd.Series([True] * len(df))

    if not show_all and "date" in df.columns:
        cutoff = pd.Timestamp.today() - pd.Timedelta(days=60)
        mask &= (df["date"] >= cutoff)

    if search_term:
        q = search_term.lower()
        for c in ("payee", "category", "amount"):
            if c not in df.columns:
                df[c] = ""
        mask &= (
            df["payee"].astype(str).str.lower().str.contains(q, na=False)
            | df["category"].astype(str).str.lower().str.contains(q, na=False)
            | df["amount"].astype(str).str.contains(q, na=False)
        )

    filtered_df = df[mask].sort_values(by="date", ascending=False).reset_index(drop=True)

    edited_df = st.data_editor(
        filtered_df,
        num_rows="dynamic",
        key="tx_editor",
        use_container_width=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "date": st.column_config.DateColumn("Date", format="DD.MM.YYYY"),
            "type": st.column_config.SelectboxColumn("Type", options=["Expense", "Income", "Transfer"]),
            "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
        },
        hide_index=True,
    )

    if st.button("💾 Save Changes", type="primary", use_container_width=True):
        try:
            # Detect deletions
            orig_ids = set(filtered_df.get("id", pd.Series(dtype=float)).dropna().unique())
            new_ids = set(edited_df.get("id", pd.Series(dtype=float)).dropna().unique())
            to_delete = orig_ids - new_ids

            for d_id in to_delete:
                execute_query_db(
                    "DELETE FROM transactions WHERE id = :id AND user_id = :uid",
                    {"id": int(d_id), "uid": user_id},
                )

            # Save updates/inserts
            saved = 0
            for rec in edited_df.to_dict(orient="records"):
                # Normalize NaNs
                for k, v in list(rec.items()):
                    if v is pd.NaT or pd.isna(v):
                        rec[k] = None
                rec["user_id"] = user_id

                # Use save_data_db if available; else do manual update/insert
                if save_data_db("transactions", rec):
                    saved += 1
                else:
                    # fallback: if save_data_db missing or failed, do a direct update/insert
                    if rec.get("id"):
                        _id = rec.pop("id")
                        set_clause = ", ".join([f"{k} = :{k}" for k in rec.keys()])
                        execute_query_db(
                            f"UPDATE transactions SET {set_clause} WHERE id = :id AND user_id = :uid",
                            {**rec, "id": _id, "uid": user_id},
                        )
                        saved += 1
                    else:
                        # insert without id
                        rec.pop("id", None)
                        if add_record_db:
                            add_record_db("transactions", rec)
                            saved += 1

            st.success(f"✅ Saved {saved} row(s).")
            st.rerun()
        except Exception as e:
            st.error(f"Error saving changes: {e}")


def render_export_section():
    st.subheader("📤 Export Your Data")
    user_id = _get_user_id()

    if st.button("🚀 Generate Backup (Excel)", use_container_width=True):
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                for table in USER_DATA_TABLES:
                    df = load_data_db(table, user_id=user_id)
                    if df is None or df.empty:
                        pd.DataFrame().to_excel(writer, sheet_name=table, index=False)
                        continue

                    # Remove timezone info if any
                    for c in df.columns:
                        if pd.api.types.is_datetime64_any_dtype(df[c]):
                            try:
                                df[c] = df[c].dt.tz_localize(None)
                            except Exception:
                                pass

                    df.to_excel(writer, sheet_name=table, index=False)

            st.download_button(
                "📥 Download Backup",
                buffer.getvalue(),
                file_name=f"backup_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
            st.success("✅ Backup generated.")
        except Exception as e:
            st.error(f"Export failed: {e}")


def render_import_section():
    st.subheader("📥 Import & Restore Data")
    user_id = _get_user_id()

    st.warning(f"⚠️ This will replace data for **{user_id}** for any sheets you restore.")

    f = st.file_uploader("Backup File (.xlsx)", type=["xlsx"])

    col_a, col_b = st.columns([1, 1])
    with col_a:
        confirm = st.checkbox("I understand this will overwrite my data", value=False)
    with col_b:
        restore_btn = st.button("🔄 Restore", type="primary", use_container_width=True, disabled=not (f and confirm))

    if not (f and restore_btn):
        return

    if add_record_db is None:
        st.error("Import requires add_record_db(). It is missing in core.db_operations.")
        return

    try:
        xls = pd.ExcelFile(f)
        restored_tables = 0

        for sheet in xls.sheet_names:
            if sheet not in USER_DATA_TABLES:
                continue

            try:
                df = pd.read_excel(xls, sheet_name=sheet)
                if df is None or df.empty:
                    continue

                # Clean & prepare records
                records = _clean_records_for_db(df, sheet, user_id)
                if not records:
                    continue

                # Delete old data
                execute_query_db(f"DELETE FROM {sheet} WHERE user_id = :uid", {"uid": user_id})

                # Insert new
                add_record_db(sheet, records)
                restored_tables += 1

            except Exception as ex:
                st.error(f"❌ {sheet}: {ex}")

        if restored_tables > 0:
            st.success(f"✅ Restored {restored_tables} table(s).")
            st.rerun()
        else:
            st.info("No matching sheets restored.")
    except Exception as e:
        st.error(f"Import Error: {e}")


def render_cleanup_section():
    st.subheader("🗑️ Data Cleanup")
    user_id = _get_user_id()

    if st.button("🔍 Remove Duplicate Transactions", use_container_width=True):
        df = load_data_db("transactions", user_id=user_id)
        if df is None or df.empty:
            st.info("No transactions to clean.")
            return

        start = len(df)
        subset_cols = [c for c in ["date", "account", "category", "payee", "amount"] if c in df.columns]
        clean = df.drop_duplicates(subset=subset_cols)

        removed = start - len(clean)
        if removed <= 0:
            st.info("No duplicates found.")
            return

        try:
            execute_query_db("DELETE FROM transactions WHERE user_id = :uid", {"uid": user_id})
            recs = _clean_records_for_db(clean, "transactions", user_id)

            if add_record_db is None:
                st.error("Cleanup requires add_record_db(). It is missing in core.db_operations.")
                return

            add_record_db("transactions", recs)
            st.success(f"✅ Removed {removed} duplicates.")
            st.rerun()
        except Exception as e:
            st.error(f"Cleanup failed: {e}")

    st.divider()

    table = st.selectbox("Clear Table", [""] + USER_DATA_TABLES)
    if table and st.button(f"💥 Clear {table}", use_container_width=True):
        try:
            execute_query_db(f"DELETE FROM {table} WHERE user_id = :uid", {"uid": user_id})
            st.success("✅ Cleared.")
            st.rerun()
        except Exception as e:
            st.error(f"Clear failed: {e}")
