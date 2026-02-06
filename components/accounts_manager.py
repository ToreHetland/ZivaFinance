# components/accounts_manager.py
from __future__ import annotations
import calendar
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta

from config.i18n import t

# ============================================================
# DB OPS (Cloud-safe imports)
# ============================================================
from core.db_operations import load_data_db, add_record_db, execute_query_db

# Optional helpers (don’t crash the app if missing in db_operations.py)
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

try:
    from core.db_operations import normalize_date_to_iso
except ImportError:
    def normalize_date_to_iso(x):
        return x


# ============================================================
# CONSTANTS & HELPERS
# ============================================================
CARD_STYLE = """
    background:#fff;
    border:1px solid rgba(0,0,0,0.1);
    border-radius:12px;
    padding:20px;
    box-shadow:0 2px 12px rgba(0,0,0,0.08);
"""

ACCOUNT_TYPE_ICONS = {
    "Checking": "🏦",
    "Savings": "💰", 
    "Credit Card": "💳",
    "Loan": "🏦",
    "Investment": "📈",
    "Cash": "💵",
}

CURRENCY_OPTIONS = [
    "NOK", "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY", "CHF", "SEK", "DKK"
]

def _ensure_account_schema(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = [
        "name", "account_type", "balance", "currency", "is_default",
        "credit_interest_rate", "credit_due_day", "credit_source_account", 
        "credit_period_mode", "credit_start_day", "credit_end_day",
        "description", "created_date", "last_updated"
    ]
    
    if df.empty:
        df = pd.DataFrame(columns=required_cols)
    else:
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
    
    # Set default values
    df["currency"] = df["currency"].fillna("NOK").astype(str)
    df["account_type"] = df["account_type"].fillna("Checking").astype(str)
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce").fillna(0.0)
    df["credit_interest_rate"] = pd.to_numeric(df["credit_interest_rate"], errors="coerce").fillna(0.0)
    df["credit_due_day"] = pd.to_numeric(df["credit_due_day"], errors="coerce").fillna(20)
    df["credit_start_day"] = pd.to_numeric(df["credit_start_day"], errors="coerce").fillna(1)
    df["credit_end_day"] = pd.to_numeric(df["credit_end_day"], errors="coerce").fillna(31)
    
    df["is_default"] = df["is_default"].fillna(False).infer_objects(copy=False).astype(bool)
    
    df["description"] = df["description"].fillna("").astype(str)
    df["credit_source_account"] = df["credit_source_account"].fillna("").astype(str)
    df["credit_period_mode"] = df["credit_period_mode"].fillna("Previous Month").astype(str)
    df["credit_source_account"] = df["credit_source_account"].replace("nan", "")
    
    current_date = datetime.now()
    df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce").fillna(current_date)
    df["last_updated"] = pd.to_datetime(df["last_updated"], errors="coerce").fillna(current_date)
    
    return df

def _validate_account_data(df: pd.DataFrame) -> tuple[bool, str]:
    if df.empty: return True, ""
    if df["name"].duplicated().any():
        return False, "Duplicate account names found"
    return True, ""

# ============================================================
# 🧮 EXACT MATH SYNC (Updated with CC Settlement Logic)
# ============================================================
def _get_signed_amount(row) -> float:
    """Centralized logic for calculating the actual +/- value of a transaction."""
    try:
        amt = float(row.get("amount", 0))
    except:
        amt = 0.0
        
    t = str(row.get("type", "")).strip().lower()
    
    # Positive Types
    if t in ["income", "opening balance", "deposit", "refund"]:
        return amt
    # Negative Types
    elif t in ["expense", "transfer", "withdrawal", "payment"]:
        return -abs(amt)
    
    return 0.0

def get_statement_balance(card_name: str, billing_month: int, billing_year: int, user_id: str) -> float:
    """Calculates the net debt accumulated during a specific month for ONE user."""
    tx_df = load_data_db("transactions", user_id=user_id)
    if tx_df is None or tx_df.empty:
        return 0.0

    tx_df["date_dt"] = pd.to_datetime(tx_df["date"], errors="coerce")
    card_tx = tx_df[tx_df["account"] == card_name].copy()

    statement_period = card_tx[
        (card_tx["date_dt"].dt.month == billing_month) &
        (card_tx["date_dt"].dt.year == billing_year)
    ]

    net_val = statement_period.apply(_get_signed_amount, axis=1).sum()
    return abs(net_val) if net_val < 0 else 0.0

def _get_live_balances(user_id: str) -> dict[str, float]:
    """Calculates the REAL current balance for all accounts up to TODAY for ONE user."""
    tx_df = load_data_db("transactions", user_id=user_id)
    if tx_df is None or tx_df.empty:
        return {}

    tx_df["date_dt"] = pd.to_datetime(tx_df["date"], errors="coerce").dt.date
    today = date.today()
    tx_df = tx_df[tx_df["date_dt"] <= today]

    if tx_df.empty:
        return {}

    tx_df["signed_amount"] = tx_df.apply(_get_signed_amount, axis=1)
    return tx_df.groupby("account")["signed_amount"].sum().to_dict()


def _get_account_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total_accounts": 0, "total_balance": 0.0, "by_type": {}, "default_account": None}
    
    summary = {
        "total_accounts": len(df),
        "total_balance": df["balance"].sum(),
        "by_type": df.groupby("account_type")["balance"].sum().to_dict(),
        "default_account": df[df["is_default"]]["name"].iloc[0] if df["is_default"].any() else None,
        "currency_distribution": df["currency"].value_counts().to_dict(),
    }
    
    cc = df[df["account_type"] == "Credit Card"]
    summary["credit_card_debt"] = cc["balance"].sum() if not cc.empty else 0
    summary["credit_card_count"] = len(cc)
    
    loans = df[df["account_type"] == "Loan"]
    summary["loan_debt"] = loans["balance"].sum() if not loans.empty else 0
    summary["loan_count"] = len(loans)
    
    return summary

def _render_account_card(account: pd.Series, summary: dict) -> None:
    icon = ACCOUNT_TYPE_ICONS.get(account["account_type"], "🏦")
    balance = float(account["balance"])
    
    # Determine colors and signs based on account type
    if account["account_type"] in ["Credit Card", "Loan"]:
        card_color = "#fee" if balance > 0 else "#efe"
        balance_color = "#d32f2f" if balance > 0 else "#388e3c"
        balance_sign = ""
    else:
        card_color = "#e8f5e9" if balance >= 0 else "#ffebee"
        balance_color = "#388e3c" if balance >= 0 else "#d32f2f"
        balance_sign = "+" if balance >= 0 else ""
    
    balance_display = f"{balance_sign}{balance:,.2f} {account['currency']}"
    default_str = " • ⭐ Default" if account['is_default'] else ""
    desc_html = f"<div style='font-size: 12px; color: #666; margin-top: 4px;'>{account['description']}</div>" if account['description'] else ""
    
    # Minified HTML to prevent Markdown errors
    card_html = f"<div style='background-color: {card_color}; border: 1px solid rgba(0,0,0,0.1); border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);'><div style='display: flex; justify-content: space-between; align-items: flex-start;'><div><div style='font-size: 20px; font-weight: bold; margin-bottom: 4px;'>{icon} {account['name']}</div><div style='font-size: 14px; color: #666; margin-bottom: 8px;'>{account['account_type']}{default_str}</div></div><div style='text-align: right;'><div style='font-size: 18px; font-weight: bold; color: {balance_color};'>{balance_display}</div>{desc_html}</div></div></div>"
    
    st.markdown(card_html, unsafe_allow_html=True)

# ============================================================
# ⚖️ RECONCILIATION HELPER
# ============================================================
def _calculate_system_balance(account_name: str, date_limit: date, user_id: str) -> float:
    tx_df = load_data_db("transactions", user_id=user_id)
    if tx_df is None or tx_df.empty:
        return 0.0

    tx_df = tx_df[tx_df["account"] == account_name].copy()
    tx_df["date"] = pd.to_datetime(tx_df["date"], errors="coerce")

    end_of_day = datetime.combine(date_limit, datetime.max.time())
    tx_df = tx_df[tx_df["date"] <= end_of_day]

    if tx_df.empty:
        return 0.0

    tx_df["signed"] = tx_df.apply(_get_signed_amount, axis=1)
    return float(tx_df["signed"].sum())


# ============================================================
# MAIN RENDERER
# ============================================================
def render_accounts_manager():
    st.title("🏦 Account Management")
    st.caption("Manage financial accounts, credit card monthly settlements, and reconciled balances.")
    
    uid = st.session_state.get("username") or "default"
    df = load_data_db("accounts", user_id=uid)

    df = _ensure_account_schema(df)
    
    # --- LIVE BALANCE SYNC ---
    live_balances = _get_live_balances(uid)

    if not df.empty:
        # Override the stored balance with the live calculated balance
        df["balance"] = df["name"].map(live_balances).fillna(0.0)
    
    summary = _get_account_summary(df)
    
    # --- TABBED INTERFACE ---
    tab_overview, tab_settle, tab_edit, tab_reconcile, tab_quick_add = st.tabs([
        "📊 Overview", "💳 Settlement Center", "📝 Edit All", "⚖️ Reconcile", "➕ Quick Add"
    ])
    
    # TAB 1: OVERVIEW
    with tab_overview:
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Total Accounts", summary["total_accounts"])
        with col2: st.metric("Total Net Balance", f"{summary['total_balance']:,.2f} NOK")
        with col3: st.metric("Credit Cards", summary.get("credit_card_count", 0))
        with col4: st.metric("Loans", summary.get("loan_count", 0))
        
        if summary["default_account"]:
            st.info(f"⭐ **Default Account:** {summary['default_account']}")
        
        st.markdown("---")
        
        account_types = df["account_type"].unique()
        for acc_type in account_types:
            type_accounts = df[df["account_type"] == acc_type]
            if not type_accounts.empty:
                st.subheader(f"{ACCOUNT_TYPE_ICONS.get(acc_type, '📁')} {acc_type} ({len(type_accounts)})")
                for _, account in type_accounts.iterrows():
                    _render_account_card(account, summary)
        
    # TAB 2: SETTLEMENT CENTER (The Challenge Logic)
    with tab_settle:
        st.subheader("💳 Credit Card Monthly Pay-Off")
        st.caption("Identify last month's spending and schedule payments for the 20th.")

        cards = df[df["account_type"] == "Credit Card"]
        if cards.empty:
            st.info("No credit cards found.")
        else:
            today = date.today()
            last_month_dt = today - relativedelta(months=1)

            for i, card in enumerate(cards.itertuples(index=False)):
                # card is a namedtuple now (safer/faster than iterrows)
                card_name = getattr(card, "name", "")
                card_currency = getattr(card, "currency", "NOK")
                source_acc = getattr(card, "credit_source_account", None)
                due_day_raw = getattr(card, "credit_due_day", 20)
                card_id = getattr(card, "id", None)  # may or may not exist

                # Amount due (based on last month's statement)
                amt_due = get_statement_balance(card_name, last_month_dt.month, last_month_dt.year, uid)

                # Safe due date: clamp due_day to last day in month
                try:
                    due_day = int(due_day_raw) if due_day_raw is not None else 20
                except Exception:
                    due_day = 20
                last_dom = calendar.monthrange(today.year, today.month)[1]
                due_day = max(1, min(due_day, last_dom))
                due_date = date(today.year, today.month, due_day)

                # Unique button key (fixes StreamlitDuplicateElementKey)
                safe_name = str(card_name).strip().lower().replace(" ", "_")
                unique_key = f"pay_{card_id if card_id is not None else i}_{safe_name}_{last_month_dt.year}{last_month_dt.month:02d}"

                with st.expander(f"{card_name} Settlement - {last_month_dt.strftime('%B %Y')}", expanded=amt_due > 0):
                    c1, c2 = st.columns(2)
                    c1.metric("Debt from Last Month", f"{amt_due:,.2f} {card_currency}")
                    c2.write(f"**Target Payment Date:** {due_date.strftime('%d.%m.%Y')}")
                    c2.write(f"**Pay From:** {source_acc if source_acc else '🚨 Set in Edit Tab'}")

                    if amt_due > 0 and source_acc:
                        if st.button(f"Confirm & Pay {amt_due:,.2f}", key=unique_key):
                            # Payment deduction from Brukskonto (source)
                            out_tx = {
                                "date": normalize_date_to_iso(due_date),
                                "type": "Expense",
                                "account": source_acc,
                                "category": "Transfer",
                                "payee": f"Full Settlement: {card_name}",
                                "amount": float(amt_due),
                                "description": f"Paid full balance from {last_month_dt.strftime('%B %Y')}",
                                "initials": "SYS",
                                "user_id": st.session_state.get("username", "default"),
                            }

                            # Payment credit to Card (destination)
                            in_tx = out_tx.copy()
                            in_tx["type"] = "Income"
                            in_tx["account"] = card_name
                            in_tx["payee"] = f"Payment from {source_acc}"

                            if add_record_db("transactions", out_tx) and add_record_db("transactions", in_tx):
                                st.success(f"✅ Scheduled for {due_date.strftime('%d.%m')}")
                                st.rerun()
                    elif amt_due > 0 and not source_acc:
                        st.warning("Set **Pay From** account in the Edit tab to enable settlement.")

    # TAB 3: EDIT ALL
    with tab_edit:
        st.subheader("Edit All Accounts")
        st.info("Edit account details directly below. Only one account can be marked as default.")
        
        if df.empty:
            st.info("No accounts found.")
        else:
            df_edit = df.copy()
            df_edit["delete"] = False
            account_names = df_edit["name"].dropna().astype(str).unique().tolist()
            
            st.markdown(f"<div style='{CARD_STYLE}'>", unsafe_allow_html=True)
            
            # 1. Get the most recent list of account names for the dropdown
            current_account_names = df["name"].dropna().unique().tolist()

            # 2. Updated Data Editor logic
            edited = st.data_editor(
                df_edit,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "delete": st.column_config.CheckboxColumn("Delete?", default=False, width="small"),
                    "name": st.column_config.TextColumn("Account Name", required=True),
                    "account_type": st.column_config.SelectboxColumn("Type", options=list(ACCOUNT_TYPE_ICONS.keys()), required=True),
                    "balance": st.column_config.NumberColumn("Initial Balance", format="%.2f", disabled=True, help="Balances are calculated from transactions."),
                    "currency": st.column_config.SelectboxColumn("Currency", options=CURRENCY_OPTIONS, default="NOK"),
                    "is_default": st.column_config.CheckboxColumn("Default?", width="small"),
                    "description": st.column_config.TextColumn("Description"),
                    "credit_interest_rate": st.column_config.NumberColumn("Interest %", format="%.1f"),
                    "credit_due_day": st.column_config.NumberColumn("Due Day", min_value=1, max_value=31),
                    
                    # FIXED: Explicitly link the dropdown to your account names
                    "credit_source_account": st.column_config.SelectboxColumn(
                        "Pay From", 
                        options=[""] + current_account_names,
                        help="Select which account is used to pay off this credit card."
                    ),
                    
                    "credit_period_mode": st.column_config.SelectboxColumn("Billing Period", options=["Previous Month", "Current Month", "Custom"]),
                },
                key="accounts_editor_main"
            )
            st.markdown("</div>", unsafe_allow_html=True)
            
            col_save, col_reset = st.columns(2)
            with col_save:
                if st.button("💾 Save All Changes", type="primary", use_container_width=True):
                    try:
                        to_save = edited[~edited["delete"]].copy()
                        if "delete" in to_save.columns: to_save = to_save.drop(columns=["delete"])
                        
                        to_save["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                        to_save["is_default"] = to_save["is_default"].fillna(False).infer_objects(copy=False).astype(bool)
                        
                        if to_save["is_default"].sum() > 1:
                            first = to_save.index[to_save["is_default"]][0]
                            to_save["is_default"] = False
                            to_save.at[first, "is_default"] = True
                        
                        is_valid, error_msg = _validate_account_data(to_save)
                        if not is_valid:
                            st.error(error_msg)
                            st.stop()
                        
                        if save_data_db("accounts", sanitize_for_db(to_save), if_exists="replace"):
                            st.success("✅ Accounts saved successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to save.")
                    except Exception as e:
                        st.error(f"Error: {e}")
            
            with col_reset:
                if st.button("🔄 Reset Changes", use_container_width=True):
                    st.rerun()

    # TAB 4: RECONCILE
    with tab_reconcile:
        st.subheader("⚖️ Correct Account Balance")
        st.caption("If your app balance doesn't match your real bank balance, enter the REAL amount below.")
        
        if df.empty:
            st.warning("No accounts available.")
        else:
            # 1. Select Account & Date
            rec_col1, rec_col2 = st.columns(2)
            
            with rec_col1:
                rec_account = st.selectbox("Select Account", df["name"].unique(), key="rec_acc_select")
                rec_date = st.date_input("As of Date", date.today(), key="rec_date_select")
            
            # 2. Show System Balance vs Input
            system_balance = _calculate_system_balance(rec_account, rec_date, uid)
            
            with rec_col2:
                st.metric("System thinks you have:", f"{system_balance:,.2f} NOK")
                
                # The user enters their REAL bank balance here
                actual_balance = st.number_input(
                    "Actual Bank Balance (What your bank app says):", 
                    value=float(system_balance), 
                    step=100.0,
                    format="%.2f"
                )
            
            # 3. Calculate Difference
            diff = actual_balance - system_balance
            
            st.divider()
            
            if abs(diff) < 0.01:
                st.success("✅ Perfect Match! No adjustment needed.")
            else:
                st.warning(f"⚠️ Difference Detected: {diff:,.2f} NOK")
                st.write(f"Clicking the button below will create a transaction of **{abs(diff):,.2f}** to fix this.")
                
                if st.button(f"🛠️ Fix Balance Now", type="primary", use_container_width=True):
                    # Create the adjustment transaction
                    tx_type = "Income" if diff > 0 else "Expense"
                    amount = abs(diff)
                    
                    adjustment_record = {
                        "date": normalize_date_to_iso(rec_date),
                        "type": tx_type,
                        "account": rec_account,
                        "category": "Balance Adjustment",
                        "payee": "Manual Correction",
                        "amount": float(amount),
                        "description": f"Reconciled to match bank balance of {actual_balance}",
                        "initials": "SYS"
                    }
                    
                    if add_record_db("transactions", adjustment_record):
                        st.cache_data.clear() 
                        st.balloons()
                        st.success("✅ Balance corrected successfully!")
                        import time
                        time.sleep(1.0)
                        st.rerun()
                    else:
                        st.error("Failed to create adjustment transaction.")

   # TAB 5: QUICK ADD
with tab_quick_add:
    st.subheader("Add New Account")

    # Ensure we always work on the active user only
    uid = st.session_state.get("username") or "default"

    # IMPORTANT: Put Account Type OUTSIDE the form so selecting "Credit Card" triggers a rerun
    st.selectbox(
        "Account Type*",
        options=list(ACCOUNT_TYPE_ICONS.keys()),
        key="qa_type"
    )

    is_cc = (st.session_state.get("qa_type") == "Credit Card")

    if is_cc:
        st.info("💳 Credit Card selected — please fill in the extra credit card settings below before saving.")

    with st.form("quick_add_account_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Account Name*", placeholder="e.g., Norwegian Visa", key="qa_name")
            st.number_input("Starting Balance*", value=0.0, format="%.2f", key="qa_bal")

        with col2:
            st.selectbox("Currency*", options=CURRENCY_OPTIONS, index=0, key="qa_curr")
            st.checkbox("Set as default account", value=False, key="qa_def")
            st.text_input("Description", placeholder="Optional notes", key="qa_desc")

        # Credit-card-only fields
        if is_cc:
            st.markdown("---")
            st.markdown("### 💳 Credit Card Settings")

            c1, c2 = st.columns(2)
            with c1:
                st.number_input("Interest Rate (%)", value=19.5, step=0.1, key="qa_ir")
                st.selectbox("Billing Period", ["Previous Month", "Current Month", "Custom"], key="qa_pm")

            with c2:
                default_day = 15 if "Norwegian" in (st.session_state.get("qa_name") or "") else 20
                st.number_input(
                    "Payment Due Day (1-31)",
                    value=int(default_day),
                    min_value=1,
                    max_value=31,
                    key="qa_dd"
                )

                # ✅ user-scoped accounts list
                acc_df = load_data_db("accounts", user_id=uid)
                fresh_acc_list = acc_df["name"].dropna().tolist() if acc_df is not None and not acc_df.empty else []
                st.selectbox(
                    "Auto-pay From (Funding Account)",
                    options=[""] + fresh_acc_list,
                    key="qa_src"
                )

            if st.session_state.get("qa_pm") == "Custom":
                cs1, cs2 = st.columns(2)
                cs1.number_input("Start Day", 1, 31, 1, key="qa_sd")
                cs2.number_input("End Day", 1, 31, 31, key="qa_ed")

        submitted = st.form_submit_button("➕ Add Account", type="primary", use_container_width=True)

        if submitted:
            final_name = (st.session_state.get("qa_name") or "").strip()
            if not final_name:
                st.error("Account name is required.")
                st.stop()

            # ✅ duplicate check ONLY for this user
            df_check = load_data_db("accounts", user_id=uid)
            if df_check is not None and not df_check.empty and final_name in df_check["name"].astype(str).values:
                st.error(f"Account '{final_name}' already exists. Delete it in 'Edit All' if it's a mistake.")
                st.stop()

            if is_cc:
                ir = float(st.session_state.get("qa_ir", 19.5))
                dd = int(st.session_state.get("qa_dd", 20))
                src = (st.session_state.get("qa_src") or "").strip()
                pm  = st.session_state.get("qa_pm", "Previous Month")
                sd  = int(st.session_state.get("qa_sd", 1))
                ed  = int(st.session_state.get("qa_ed", 31))
            else:
                ir, dd, src, pm, sd, ed = 0.0, 20, "", "Previous Month", 1, 31

            created_dt = datetime.now().strftime("%Y-%m-%d")

            data = {
                "name": final_name,
                "account_type": st.session_state.get("qa_type"),
                "balance": float(st.session_state.get("qa_bal", 0.0)),
                "currency": st.session_state.get("qa_curr"),
                "is_default": bool(st.session_state.get("qa_def", False)),
                "description": (st.session_state.get("qa_desc") or "").strip(),
                "created_date": created_dt,
                "last_updated": created_dt,

                # Credit-card fields (safe even if not CC)
                "credit_interest_rate": ir,
                "credit_due_day": dd,
                "credit_source_account": src,
                "credit_period_mode": pm,
                "credit_start_day": sd,
                "credit_end_day": ed,

                # ✅ THIS WAS MISSING
                "user_id": uid,
            }

            if add_record_db("accounts", data):
                # ✅ opening balance transaction should belong to same user
                opening_bal = float(data["balance"] or 0.0)
                if abs(opening_bal) > 0:
                    add_record_db("transactions", {
                        "date": created_dt,
                        "type": "Income" if opening_bal > 0 else "Expense",
                        "account": data["name"],
                        "category": "Opening Balance",
                        "payee": "Opening Balance",
                        "amount": abs(opening_bal),
                        "description": "Initial account balance",
                        "initials": "SYS",
                        "user_id": uid,  # ✅ THIS WAS MISSING
                    })

                st.cache_data.clear()
                st.success(f"✅ Added {final_name} successfully!")
                st.rerun()
