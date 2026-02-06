# components/transactions_page.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import ast
import tempfile
import time

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta

# ============================================================
# OPTIONAL VOICE SUPPORT (streamlit-mic-recorder)
# ============================================================
try:
    from streamlit_mic_recorder import mic_recorder  # type: ignore
    MIC_AVAILABLE = True
except Exception:
    mic_recorder = None
    MIC_AVAILABLE = False

# ============================================================
# AI PARSER (Gemini)
# ============================================================
from core.ai_parser import parse_transaction_with_gemini

# ============================================================
# DB OPS (Cloud-safe imports)
# ============================================================
from core.db_operations import load_data_db, add_record_db, execute_query_db

# Optional helpers: keep app running even if db_operations changes
try:
    from core.db_operations import normalize_date_to_iso
except ImportError:
    def normalize_date_to_iso(x):
        return x

try:
    from core.db_operations import normalize_type
except ImportError:
    def normalize_type(x) -> str:
        return (str(x).strip().lower() if x is not None else "")

try:
    from core.db_operations import ensure_category_exists
except ImportError:
    def ensure_category_exists(*args, **kwargs):
        return None

try:
    from core.db_operations import ensure_payee_exists
except ImportError:
    def ensure_payee_exists(*args, **kwargs):
        return None

try:
    from core.db_operations import get_category_type
except ImportError:
    def get_category_type(*args, **kwargs) -> str:
        return "expense"

# ============================================================
# OPTIONAL LOCAL WHISPER SUPPORT (faster-whisper)
# ============================================================
try:
    import faster_whisper  # type: ignore
    WHISPER_AVAILABLE = True
except Exception:
    WHISPER_AVAILABLE = False

# ============================================================
# 🔐 USER CONTEXT
# ============================================================
def _get_user_id() -> str:
    uid = st.session_state.get("username")
    uid = str(uid).strip() if uid is not None else ""
    return uid or "default"

# ============================================================
# 🎙️ WHISPER
# ============================================================
@st.cache_resource(show_spinner=False)
def _get_whisper_model():
    if not WHISPER_AVAILABLE:
        return None
    try:
        from faster_whisper import WhisperModel
    except Exception:
        return None
    return WhisperModel("small", device="cpu", compute_type="int8")

def transcribe_mic_audio(audio: dict) -> str:
    try:
        if not isinstance(audio, dict): return ""
        if not WHISPER_AVAILABLE: return ""
        b = audio.get("bytes")
        if not b: return ""
        if isinstance(b, str):
            s = b.strip()
            if s.startswith(("b'", 'b"')):
                try:
                    b = ast.literal_eval(s)
                except Exception: return ""
            else: return ""
        if not isinstance(b, (bytes, bytearray)): return ""
        fmt = (audio.get("format") or "webm").lower().strip(".")
        suffix = f".{fmt}" if fmt else ".webm"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                f.write(b)
                tmp_path = f.name
            model = _get_whisper_model()
            if model is None: return ""
            segments, _info = model.transcribe(tmp_path, beam_size=5, vad_filter=True)
            return " ".join((seg.text or "").strip() for seg in segments).strip()
        finally:
            try:
                if tmp_path and Path(tmp_path).exists():
                    Path(tmp_path).unlink(missing_ok=True)
            except Exception: pass
    except Exception as e:
        st.warning(f"Whisper transcription failed: {e}")
        return ""

# ============================================================
# 🧮 SHARED MATH LOGIC
# ============================================================
def _get_signed_amount(row) -> float:
    try:
        amt = float(row.get("amount", 0) or 0)
    except Exception:
        amt = 0.0
    t = str(row.get("type", "")).strip().lower()
    
    if t in ["income", "deposit", "refund"]:
        return amt
    if t in ["expense", "transfer", "withdrawal", "payment"]:
        return -abs(amt)
    # Important: Opening Balance is returned AS IS. 
    # For a loan, the user should enter a negative number, or we handle the sign at entry.
    if t == "opening balance":
        return amt
        
    return 0.0

def _compute_account_balances(df_all: pd.DataFrame) -> dict[str, float]:
    """
    Calculates the current balance for every account based on the ledger.
    IMPORTANT: Filters out future transactions to show 'Balance As Of Today'.
    """
    if df_all is None or df_all.empty:
        return {}
    
    df = df_all.copy()
    
    # 1. Robust Date Parsing
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    today = date.today()
    
    # 2. Filter: Only sum transactions up to today.
    # Fill NaT with today to be safe so we don't lose data
    df["date_dt"] = df["date_dt"].fillna(today)
    
    df_current = df[df["date_dt"] <= today].copy()
    
    # 3. Compute
    df_current["signed"] = df_current.apply(_get_signed_amount, axis=1)
    return df_current.groupby("account")["signed"].sum().to_dict()

def _upsert_settlement_transfer(selected_account: str, amount_val: float, date_val: str | date):
    user_id = _get_user_id()
    acc_df = load_data_db("accounts", user_id=user_id)
    if acc_df is None or acc_df.empty or selected_account not in acc_df["name"].astype(str).values:
        return
    this_acc = acc_df[acc_df["name"].astype(str) == str(selected_account)].iloc[0]
    if str(this_acc.get("account_type", "")).strip() != "Credit Card":
        return
    trans_date = pd.to_datetime(date_val, errors="coerce")
    if pd.isna(trans_date): return
    due_day = int(this_acc.get("credit_due_day", 20) or 20)
    settlement_date = (trans_date + relativedelta(months=1)).replace(day=due_day).strftime("%Y-%m-%d")
    source_account = this_acc.get("credit_source_account") or "Brukskonto"
    tx_df = load_data_db("transactions", user_id=user_id)
    if tx_df is None or tx_df.empty: return
    tx_df = tx_df.copy()
    tx_df["date_dt"] = pd.to_datetime(tx_df.get("date"), errors="coerce")
    month_mask = (
        (tx_df.get("account").astype(str) == str(selected_account))
        & (tx_df["date_dt"].dt.month == trans_date.month)
        & (tx_df["date_dt"].dt.year == trans_date.year)
        & (~tx_df.get("description", "").astype(str).str.contains("Auto-settle", na=False))
    )
    monthly_net_total = tx_df.loc[month_mask].apply(_get_signed_amount, axis=1).sum()
    target_transfer_amount = abs(monthly_net_total) if monthly_net_total < 0 else 0.0
    existing_mask = (
        (tx_df.get("user_id", "").astype(str) == str(user_id))
        & (tx_df.get("date").astype(str) == str(settlement_date))
        & (tx_df.get("account").astype(str) == str(selected_account))
        & (tx_df.get("category", "").astype(str) == "Transfer")
        & (tx_df.get("description", "").astype(str).str.contains("Auto-settle", na=False))
    )
    if not tx_df.loc[existing_mask].empty:
        update_sql = "UPDATE transactions SET amount = :amt WHERE user_id = :uid AND date = :dt AND account = :acc AND description LIKE '%Auto-settle%'"
        execute_query_db(update_sql, {"amt": float(target_transfer_amount), "uid": user_id, "dt": settlement_date, "acc": selected_account})
        return
    out_transfer = {
        "user_id": user_id, "date": settlement_date, "amount": float(target_transfer_amount),
        "type": "expense", "account": str(source_account), "category": "Transfer",
        "payee": f"Settlement: {selected_account}", "description": f"Auto-settle for {selected_account}",
    }
    in_transfer = out_transfer.copy()
    in_transfer["type"] = "income"
    in_transfer["account"] = str(selected_account)
    in_transfer["payee"] = f"From {source_account}"
    add_record_db("transactions", out_transfer)
    add_record_db("transactions", in_transfer)

# ============================================================
# ✨ AI SMART ENTRY
# ============================================================
def render_ai_smart_entry(selected_account: str):
    st.markdown(
        """<div class="ziva-sidebar-card"><h4 style="margin: 0; color: #2c3e50; font-size: 14px; font-weight: bold;">✨ AI Smart Entry</h4></div>""",
        unsafe_allow_html=True,
    )
    user_id = _get_user_id()
    voice_col, _ = st.columns([1, 4])
    st.session_state.setdefault("voice_transcript", "")
    audio = None
    with voice_col:
        if MIC_AVAILABLE:
            audio = mic_recorder(start_prompt="🎙️", stop_prompt="🛑", key="voice_recorder_widget", use_container_width=True)
        else:
            st.button("🎙️", disabled=True, use_container_width=True)
    if MIC_AVAILABLE and audio:
        if isinstance(audio, dict) and audio.get("text"):
            st.session_state["voice_transcript"] = str(audio["text"]).strip()
        else:
            st.session_state["voice_transcript"] = (transcribe_mic_audio(audio) or "").strip()
    query = st.text_area("AI Input", value=st.session_state.get("voice_transcript", ""), placeholder='e.g. "Spent 250 NOK on groceries"', height=70, label_visibility="collapsed", key="ai_entry_widget")
    st.session_state["voice_transcript"] = query
    if st.button("⚡ Autofill & Save", use_container_width=True, type="primary", key="ai_entry_btn"):
        if not query.strip():
            st.warning("Type something first.")
            return
        with st.spinner("AI Processing..."):
            existing_cats = _load_categories()
            data = parse_transaction_with_gemini(query, existing_cats)
            if not data:
                st.error("AI could not parse input.")
                return
            record = {
                "user_id": user_id, "date": normalize_date_to_iso(data.get("date")), "type": normalize_type(data.get("type", "expense")),
                "account": selected_account, "category": data.get("category", "Uncategorized"), "payee": data.get("payee", "Unknown"),
                "amount": float(data.get("amount", 0) or 0), "description": data.get("description", "AI Entry"),
            }
            ensure_payee_exists(record["payee"], user_id)
            ensure_category_exists(record["category"], record["type"], user_id)
            add_record_db("transactions", record)
            _upsert_settlement_transfer(selected_account, record["amount"], record["date"])
            st.success(f"✅ Saved: {record['payee']} - {record['amount']}")
            _invalidate_cache()
            time.sleep(0.2)
            st.rerun()

# ============================================================
# CACHING & DATA LOADERS
# ============================================================
@st.cache_data(ttl=30)
def _load_transactions(version: int) -> pd.DataFrame:
    user_id = _get_user_id()
    df = load_data_db("transactions", user_id=user_id)
    if df is None or df.empty:
        return pd.DataFrame(columns=["id", "date", "type", "account", "category", "payee", "amount", "description", "user_id"])
    return df.copy()

@st.cache_data(ttl=30)
def _load_accounts() -> list[str]:
    user_id = _get_user_id()
    acc = load_data_db("accounts", user_id=user_id)
    return sorted(acc["name"].dropna().astype(str).unique().tolist()) if acc is not None and not acc.empty else []

@st.cache_data(ttl=30)
def _load_loans_as_accounts() -> list[str]:
    user_id = _get_user_id()
    loans = load_data_db("loans")
    if loans is not None and not loans.empty:
        if 'user_id' in loans.columns:
            loans = loans[loans['user_id'].astype(str) == str(user_id)]
        return sorted(loans["name"].dropna().astype(str).unique().tolist())
    return []

@st.cache_data(ttl=30)
def _load_categories() -> list[str]:
    user_id = _get_user_id()
    official_cats = set()
    cat_df = load_data_db("categories", user_id=user_id)
    if cat_df is not None and not cat_df.empty:
        official_cats = set(cat_df["name"].dropna().astype(str).unique())
    used_cats = set()
    tx_df = load_data_db("transactions", user_id=user_id)
    if tx_df is not None and not tx_df.empty:
        used_cats = set(tx_df["category"].dropna().astype(str).unique())
    return sorted(list(official_cats.union(used_cats)))

@st.cache_data(ttl=30)
def _load_payees() -> list[str]:
    user_id = _get_user_id()
    official_payees = set()
    pay_df = load_data_db("payees", user_id=user_id)
    if pay_df is not None and not pay_df.empty:
        official_payees = set(pay_df["name"].dropna().astype(str).unique())
    used_payees = set()
    tx_df = load_data_db("transactions", user_id=user_id)
    if tx_df is not None and not tx_df.empty:
        used_payees = set(tx_df["payee"].dropna().astype(str).unique())
    return sorted(list(official_payees.union(used_payees)))

def _invalidate_cache():
    st.session_state["tx_data_version"] = int(st.session_state.get("tx_data_version", 0)) + 1
    _load_transactions.clear()
    _load_accounts.clear()
    _load_loans_as_accounts.clear()
    _load_categories.clear()
    _load_payees.clear()

def _with_money_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["signed_amount"] = out.apply(_get_signed_amount, axis=1)
    
    out = out.sort_values(by="date", ascending=True)
    out["Balance"] = out["signed_amount"].cumsum()
    
    out["Out"] = out["signed_amount"].apply(lambda x: x if x < 0 else 0.0)
    out["In"] = out["signed_amount"].apply(lambda x: x if x > 0 else 0.0)
    
    return out.sort_values(by="date", ascending=False)

# ============================================================
# 🟢 DIALOGS
# ============================================================
@st.dialog("Add Transaction", width="large")
def _dialog_add_transaction(selected_account: str):
    user_id = _get_user_id()
    st.caption(f"Account: **{selected_account}**")
    tab_one, tab_rec = st.tabs(["One-Time", "Recurring / Bulk"])
    cat_list = ["➕ Add New..."] + _load_categories()
    all_payees = _load_payees()
    with tab_one:
        c1, c2 = st.columns([1, 1])
        amount_val = c1.number_input("Amount", min_value=0.0, step=10.0, format="%.2f", value=None, placeholder="0.00")
        date_val = c2.date_input("Date", value=date.today())
        st.session_state.setdefault("tx_payee_smart", "")
        def _set_payee(name: str): st.session_state["tx_payee_smart"] = name
        payee_val = st.text_input("Payee", value=st.session_state["tx_payee_smart"], key="payee_input_widget", placeholder="e.g. Kiwi").strip()
        if payee_val != st.session_state["tx_payee_smart"]: st.session_state["tx_payee_smart"] = payee_val
        if payee_val:
            matches = [p for p in all_payees if payee_val.lower() in p.lower() and p.lower() != payee_val.lower()]
            if matches:
                cols = st.columns(min(len(matches), 4))
                for i, match in enumerate(matches[:4]):
                    if cols[i].button(match, key=f"btn_sug_{match}"):
                        _set_payee(match)
                        st.rerun()
        category_val = st.selectbox("Category", options=cat_list)
        final_type = "expense"
        new_cat_name = ""
        if category_val == "➕ Add New...":
            cc1, cc2 = st.columns([2, 1])
            new_cat_name = cc1.text_input("New Category Name")
            final_type = normalize_type(cc2.selectbox("Type", ["Expense", "Income"]))
        else:
            final_type = normalize_type(get_category_type(category_val, user_id) or "expense")
        desc_val = st.text_input("Description (Optional)")
        if st.button("💾 Save Record", use_container_width=True, type="primary"):
            if not payee_val or not amount_val: st.error("Missing Payee or Amount."); return
            actual_cat = new_cat_name.strip() if category_val == "➕ Add New..." else category_val
            ensure_payee_exists(payee_val, user_id)
            ensure_category_exists(actual_cat, final_type, user_id)
            new_record = {
                "user_id": user_id, "date": normalize_date_to_iso(date_val), "amount": float(amount_val),
                "type": final_type, "payee": payee_val, "category": actual_cat, "description": desc_val, "account": selected_account,
            }
            add_record_db("transactions", new_record)
            _upsert_settlement_transfer(selected_account, float(amount_val), date_val)
            st.success("Saved!"); st.session_state["tx_payee_smart"] = ""; _invalidate_cache(); time.sleep(0.2); st.rerun()

    with tab_rec:
        with st.form("tx_add_recurring", clear_on_submit=True):
            r_c1, r_c2, r_c3 = st.columns(3)
            r_start_date = r_c1.date_input("Start Date", value=date.today())
            r_freq = r_c2.selectbox("Frequency", ["Monthly", "Weekly", "Yearly"])
            r_count = r_c3.number_input("Count", min_value=2, max_value=60, value=12)
            r_cat = st.selectbox("Category", options=_load_categories(), key="rec_cat")
            r_payee = st.text_input("Payee", key="rec_payee")
            r_amt = st.number_input("Amount", min_value=0.0, format="%.2f", key="rec_amt")
            if st.form_submit_button("🚀 Generate Transactions", use_container_width=True, type="primary"):
                if not r_payee or float(r_amt) == 0: st.error("Missing Data"); return
                rec_type = normalize_type(get_category_type(r_cat, user_id) or "expense")
                ensure_payee_exists(r_payee, user_id)
                current_d = r_start_date
                for i in range(int(r_count)):
                    if i > 0:
                        if r_freq == "Monthly": current_d += relativedelta(months=1)
                        elif r_freq == "Weekly": current_d += timedelta(weeks=1)
                        elif r_freq == "Yearly": current_d += relativedelta(years=1)
                    add_record_db("transactions", {
                        "user_id": user_id, "date": normalize_date_to_iso(current_d), "amount": float(r_amt),
                        "type": rec_type, "payee": r_payee, "category": r_cat, "description": f"Rec ({i+1}/{r_count})", "account": selected_account
                    })
                    _upsert_settlement_transfer(selected_account, float(r_amt), current_d)
                _invalidate_cache(); st.success("Done!"); st.rerun()

@st.dialog("New Transfer", width="large")
def _dialog_add_transfer(selected_account: str):
    user_id = _get_user_id()
    accounts = _load_accounts() + _load_loans_as_accounts()
    accounts = list(set(accounts))
    
    with st.form("tx_transfer_standalone"):
        t_c1, t_c2 = st.columns(2)
        curr_idx = accounts.index(selected_account) if selected_account in accounts else 0
        t_from = t_c1.selectbox("From Account", options=accounts, index=curr_idx)
        t_to = t_c2.selectbox("To Account", options=accounts, index=0 if curr_idx != 0 else 1)
        t_amt = st.number_input("Amount", min_value=0.0, format="%.2f", step=100.0)
        t_desc = st.text_input("Note", "Internal Transfer")
        t_date = st.date_input("Date", value=date.today())
        if st.form_submit_button("💸 Execute Transfer", use_container_width=True, type="primary"):
            if t_from == t_to or float(t_amt) <= 0: st.error("Invalid input."); return
            base = { "user_id": user_id, "date": normalize_date_to_iso(t_date), "amount": float(t_amt), "category": "Transfer", "description": t_desc }
            add_record_db("transactions", {**base, "type": "expense", "payee": f"To {t_to}", "account": t_from})
            add_record_db("transactions", {**base, "type": "income", "payee": f"From {t_from}", "account": t_to})
            _invalidate_cache(); st.rerun()

@st.dialog("Delete Future Transactions", width="medium")
def _dialog_cleanup_future(selected_account: str):
    st.warning(f"⚠️ Managing future transactions for **{selected_account}**")
    
    categories = ["(All Categories)"] + _load_categories()
    payees = ["(All Payees)"] + _load_payees()
    
    sel_cat = st.selectbox("Filter by Category", options=categories)
    sel_payee = st.selectbox("Filter by Payee", options=payees)
    
    msg = f"This will remove future records (Date > Today) for **{selected_account}**"
    if sel_cat != "(All Categories)":
        msg += f" where Category is **{sel_cat}**"
    if sel_payee != "(All Payees)":
        msg += f" and Payee is **{sel_payee}**"
    
    st.markdown(msg)
    
    if st.button("🚨 Execute Deletion", type="primary", use_container_width=True):
        user_id = _get_user_id()
        today_iso = date.today().isoformat()
        
        sql = "DELETE FROM transactions WHERE user_id = :uid AND account = :acc AND date > :today"
        params = {"uid": user_id, "acc": selected_account, "today": today_iso}
        
        if sel_cat != "(All Categories)":
            sql += " AND category = :cat"
            params["cat"] = sel_cat
        if sel_payee != "(All Payees)":
            sql += " AND payee = :payee"
            params["payee"] = sel_payee
            
        execute_query_db(sql, params)
        _invalidate_cache()
        st.success("Selected future transactions cleared.")
        time.sleep(1)
        st.rerun()

# ============================================================
# MAIN PAGE
# ============================================================
# ============================================================
# MAIN PAGE (Updated Sidebar Section)
# ============================================================
def render_transactions_page():
    st.session_state.setdefault("tx_data_version", 0)
    df_all = _load_transactions(st.session_state["tx_data_version"])

    acc_balances = _compute_account_balances(df_all)

    user_id = _get_user_id()
    accounts_df = load_data_db("accounts", user_id=user_id)
    
    accounts = sorted(accounts_df["name"].dropna().astype(str).tolist()) if accounts_df is not None and not accounts_df.empty else []
    loans = _load_loans_as_accounts()

    left_col, right_col = st.columns([1, 4], gap="large")

    with left_col:
        try: st.image("assets/icons/ziva_icon.png", width=80)
        except Exception: pass

        st.markdown("### Accounts")
        if not accounts and not loans:
            st.sidebar.info("No accounts/loans found.") # Safe fallback
            selected_account = "Default"
        else:
            all_options = accounts + loans
            st.session_state.setdefault("tx_selected_account", all_options[0])
            if st.session_state["tx_selected_account"] not in all_options:
                st.session_state["tx_selected_account"] = all_options[0]

            # FIXED: Added enumerate 'i' to guarantee unique keys even with duplicate names
            for i, acc in enumerate(accounts):
                is_active = st.session_state["tx_selected_account"] == acc
                bal = acc_balances.get(acc, 0.0)
                label = f"🏦 {acc}\n{bal:,.0f} kr"
                if st.button(label, key=f"btn_acc_{acc}_{i}", use_container_width=True, type="primary" if is_active else "secondary"):
                    st.session_state["tx_selected_account"] = acc
                    st.rerun()
            
            if loans:
                st.markdown("##### 📉 Loans")
                # FIXED: Added enumerate 'i' for Loan keys as well
                for i, ln in enumerate(loans):
                    is_active = st.session_state["tx_selected_account"] == ln
                    bal = acc_balances.get(ln, 0.0)
                    label = f"🧾 {ln}\n{bal:,.0f} kr"
                    if st.button(label, key=f"btn_loan_{ln}_{i}", use_container_width=True, type="primary" if is_active else "secondary"):
                        st.session_state["tx_selected_account"] = ln
                        st.rerun()

            selected_account = st.session_state["tx_selected_account"]


        st.markdown("---")
        render_ai_smart_entry(selected_account)

    with right_col:
        h1, h2, h3 = st.columns([2, 2, 1])
        
        current_bal = acc_balances.get(selected_account, 0.0)
        with h1:
            st.markdown(f"## {selected_account}")
            if selected_account in loans:
                st.markdown(f"**Balance:** {current_bal:,.2f} kr")
            else:
                st.caption(f"Balance: {current_bal:,.2f} kr")

        with h2:
            col_a, col_b, col_c = st.columns([1, 1, 0.5])
            with col_a:
                if st.button("➕ New Record", use_container_width=True, type="primary"):
                    _dialog_add_transaction(selected_account)
            with col_b:
                if st.button("⇄ Transfer", use_container_width=True):
                    _dialog_add_transfer(selected_account)
            with col_c:
                if st.button("🗑️", help="Delete all FUTURE transactions"):
                    _dialog_cleanup_future(selected_account)

        # --- LOAN OPENING BALANCE FIXER ---
        # If this is a loan and balance is exactly zero, the user likely needs to initialize it.
        if selected_account in loans and current_bal == 0:
            with st.expander("⚠️ Missing Opening Balance? Click to fix.", expanded=True):
                st.info(f"The balance for **{selected_account}** is 0.00 kr. If this is a new loan record, please set the starting debt below.")
                c_fix_1, c_fix_2, c_fix_3 = st.columns([2, 2, 1])
                # Default positive for input, saved as negative
                start_debt = c_fix_1.number_input("Initial Debt Amount (Positive)", value=2874000.0, step=1000.0, format="%.2f")
                start_date = c_fix_2.date_input("Start Date", value=date(2025, 1, 1))
                if c_fix_3.button("Set Balance"):
                    # Create Opening Balance Transaction
                    # Note: We save it as negative because it's debt
                    opening_tx = {
                        "user_id": user_id,
                        "date": normalize_date_to_iso(start_date),
                        "type": "Opening Balance",
                        "account": selected_account,
                        "category": "Adjustment",
                        "payee": "Opening Balance",
                        "amount": -abs(start_debt), # Ensure negative
                        "description": "Initial Loan Balance"
                    }
                    add_record_db("transactions", opening_tx)
                    _invalidate_cache()
                    st.success("Balance updated!")
                    time.sleep(1)
                    st.rerun()

        # Filter Transactions
        df_acc = (
            df_all[df_all["account"].astype(str) == str(selected_account)].copy()
            if df_all is not None and not df_all.empty
            else pd.DataFrame()
        )

        if df_acc.empty:
            st.info(f"No transactions found for {selected_account}.")
            return

        df_view = _with_money_columns(df_acc)
        display_df = df_view[["date", "category", "payee", "Out", "In", "Balance"]].copy()

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DatetimeColumn("Date", format="DD.MM.YYYY"),
                "Out": st.column_config.NumberColumn("Out", format="%.2f kr"),
                "In": st.column_config.NumberColumn("In", format="%.2f kr"),
                "Balance": st.column_config.NumberColumn("Balance", format="%.2f kr"),
            },
        )