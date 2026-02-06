# components/categories.py
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from config.i18n import t

# ============================================================
# DB OPS (Cloud-safe imports)
# ============================================================
from core.db_operations import load_data_db, add_record_db, execute_query_db

# Optional helpers (won’t crash if missing)
try:
    from core.db_operations import save_data_db
except ImportError:
    def save_data_db(*args, **kwargs):
        return False

try:
    from core.db_operations import sanitize_for_db
except ImportError:
    def sanitize_for_db(value):
        if isinstance(value, str):
            v = value.strip()
            return v if v else None
        return value


# ============================================================
# 🛠️ UTILS
# ============================================================
def _ensure_schema(df: pd.DataFrame | None) -> pd.DataFrame:
    """Ensures dataframe has required columns and clean data."""
    req = ["name", "type", "parent_category"]
    if df is None or df.empty:
        return pd.DataFrame(columns=req)
    
    out = df.copy()
    for c in req:
        if c not in out.columns: 
            out[c] = np.nan
    
    # Clean types
    out["type"] = out["type"].fillna("Expense")
    out["type"] = out["type"].apply(lambda x: "Income" if str(x).lower() == "income" else "Expense")
    out["name"] = out["name"].astype(str).str.strip()
    
    # Standardize empty values
    out["parent_category"] = out["parent_category"].replace(
        {"": None, "nan": None, "None": None, np.nan: None}
    )
    
    # Drop duplicates
    out = out.drop_duplicates(subset=["name"], keep="first").reset_index(drop=True)
    return out

@st.dialog("➕ Add New Category")
def _dialog_add_category():
    with st.form("add_cat_dialog_form"):
        name = st.text_input("Category Name", placeholder="e.g. Netflix")
        c_type = st.selectbox("Type", ["Expense", "Income"])
        
        # Load potential parents
        df = load_data_db("categories")
        parents = sorted(df["name"].unique().tolist()) if not df.empty else []
        parent = st.selectbox("Parent Category (Optional)", [""] + parents)
        
        if st.form_submit_button("Save", type="primary"):
            if not name:
                st.error("Name required.")
            else:
                record = {
                    "name": name,
                    "type": c_type,
                    "parent_category": parent if parent else None
                }
                # Check duplicate
                if not df.empty and name in df["name"].values:
                    st.error("Category already exists.")
                else:
                    if add_record_db("categories", record):
                        st.success(f"Added {name}!")
                        st.rerun()
                    else:
                        st.error("Failed to save.")

# ============================================================
# 🎨 MAIN RENDERER
# ============================================================
def render_categories():
    st.header("🗂️ Manage Categories")
    
    # 1. Load Data
    df = _ensure_schema(load_data_db("categories"))
    
    # 2. Metrics Bar
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Categories", len(df))
        c2.metric("Expenses", len(df[df["type"]=="Expense"]))
        c3.metric("Income", len(df[df["type"]=="Income"]))
    
    st.markdown("---")

    # 3. Actions Toolbar
    col_act1, col_act2 = st.columns([1, 4])
    with col_act1:
        if st.button("➕ Add Category", type="primary", use_container_width=True):
            _dialog_add_category()
            
    # 4. Main Editor Grid
    if df.empty:
        st.info("No categories found. Click 'Add Category' to start.")
        return

    # Prepare for editor
    df_edit = df.copy()
    # Add a 'delete' checkbox column for easy removal
    df_edit.insert(0, "Delete", False)
    
    # Get options for dropdowns
    all_cats = sorted(df["name"].astype(str).unique().tolist())

    st.caption("📝 Edit any cell directly. Check the box to delete. Click **Save Changes** when done.")
    
    edited_df = st.data_editor(
        df_edit,
        column_config={
            "Delete": st.column_config.CheckboxColumn("🗑️", width="small"),
            "name": st.column_config.TextColumn("Category Name", required=True),
            "type": st.column_config.SelectboxColumn("Type", options=["Expense", "Income"], required=True, width="small"),
            "parent_category": st.column_config.SelectboxColumn("Parent Group", options=all_cats, width="medium"),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="cat_main_editor"
    )

    # 5. Save Button
    if st.button("💾 Save Changes", type="primary"):
        # Process the edited dataframe
        try:
            # Filter out deleted rows
            to_save = edited_df[~edited_df["Delete"]].copy()
            to_save = to_save.drop(columns=["Delete"])
            
            # Basic Validation: Circular Parent
            for i, row in to_save.iterrows():
                if row["parent_category"] == row["name"]:
                    to_save.at[i, "parent_category"] = None # Auto-fix circular ref
            
            # Save to DB
            if save_data_db("categories", sanitize_for_db(to_save), if_exists="replace"):
                st.success("Changes saved successfully!")
                st.rerun()
            else:
                st.error("Failed to save to database.")
                
        except Exception as e:
            st.error(f"Error saving: {e}")