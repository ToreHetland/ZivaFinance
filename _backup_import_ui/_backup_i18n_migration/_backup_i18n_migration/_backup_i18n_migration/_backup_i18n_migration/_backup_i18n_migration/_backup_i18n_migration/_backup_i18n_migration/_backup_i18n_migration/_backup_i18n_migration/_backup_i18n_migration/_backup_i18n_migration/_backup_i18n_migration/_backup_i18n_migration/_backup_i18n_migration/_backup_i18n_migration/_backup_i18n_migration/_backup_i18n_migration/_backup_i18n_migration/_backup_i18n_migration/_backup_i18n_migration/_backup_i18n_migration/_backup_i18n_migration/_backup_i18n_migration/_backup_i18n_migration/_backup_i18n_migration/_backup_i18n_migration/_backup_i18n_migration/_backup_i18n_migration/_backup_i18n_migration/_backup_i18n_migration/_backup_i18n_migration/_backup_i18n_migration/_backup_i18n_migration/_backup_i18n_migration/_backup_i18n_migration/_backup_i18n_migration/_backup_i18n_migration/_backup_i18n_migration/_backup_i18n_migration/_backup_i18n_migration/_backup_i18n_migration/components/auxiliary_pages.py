# components/auxiliary_pages.py
import streamlit as st
import pandas as pd
# Removed numpy_financial dependency to prevent errors
from core.db_operations import load_data_db, execute_query_db, add_record_db
from core.i18n import t

lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

# ==========================================
# 🏦 ACCOUNTS PAGE
# ==========================================
def render_accounts_page():
    st.subheader("💳 Manage Accounts")
    
    # 1. Add New Account
    with st.form("add_account_form", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        new_acc = c1.text_input("New Account Name")
        if c2.form_submit_button("Add Account", type="primary"):
            if new_acc:
                execute_query_db("INSERT OR IGNORE INTO accounts (name) VALUES (?)", (new_acc,))
                st.success(f"Added {new_acc}")
                st.rerun()
    
    # 2. List Accounts
    df = load_data_db("accounts")
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No accounts found.")

# ==========================================
# 🏷️ CATEGORIES PAGE
# ==========================================
def render_categories_page():
    st.subheader("🏷️ Manage Categories")
    
    # 1. Add New Category
    with st.form("add_cat_form", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        new_cat = c1.text_input("New Category Name")
        if c2.form_submit_button("Add Category", type="primary"):
            if new_cat:
                execute_query_db("INSERT OR IGNORE INTO categories (name) VALUES (?)", (new_cat,))
                st.success(f"Added {new_cat}")
                st.rerun()

    # 2. List Categories
    df = load_data_db("categories")
    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No categories found.")

# ==========================================
# 💾 DATA PAGE (Import/Export)
# ==========================================
def render_data_page():
    st.subheader("💾 Data Management")
    
    tab1, tab2 = st.tabs(["Export Data", "Import Data"])
    
    with tab1:
        st.write("Download your data as CSV.")
        df = load_data_db("transactions")
        if df is not None and not df.empty:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Transactions.csv",
                data=csv,
                file_name="transactions.csv",
                mime="text/csv",
                type="primary"
            )
        else:
            st.warning("No transactions to export.")

    with tab2:
        st.write("Upload a CSV file (Date, Description, Amount, etc.)")
        st.info("Import functionality coming soon.")

# ==========================================
# 🧮 LOAN CALCULATOR
# ==========================================
def render_loan_calculator():
    st.subheader("🧮 Loan Calculator")
    
    c1, c2, c3 = st.columns(3)
    principal = c1.number_input("Loan Amount", value=2000000, step=10000)
    rate = c2.number_input("Interest Rate (%)", value=5.5, step=0.1)
    years = c3.number_input("Years", value=25, step=1)
    
    if st.button("Calculate", type="primary"):
        # Manual Calculation (No external library needed)
        # Monthly Interest Rate
        r = (rate / 100) / 12
        # Total Number of Payments
        n = years * 12
        
        # Mortgage Formula: M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1 ]
        if r > 0:
            monthly_payment = principal * (r * (1 + r)**n) / ((1 + r)**n - 1)
        else:
            monthly_payment = principal / n
            
        st.markdown(f"### Monthly Payment: **{monthly_payment:,.2f} kr**")
        st.write(f"Total Cost of Loan: **{(monthly_payment * n):,.2f} kr**")