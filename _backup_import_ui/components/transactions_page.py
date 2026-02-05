# components/transactions_page.py
from __future__ import annotations

from datetime import date, timedelta, datetime
from pathlib import Path
import time
import ast
import tempfile

import pandas as pd
import streamlit as st
from dateutil.relativedelta import relativedelta
from config.i18n import t

lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

# --- OPTIONAL VOICE SUPPORT (MIC RECORDER) ---
try:
    from streamlit_mic_recorder import mic_recorder  # pip install streamlit-mic-recorder
    MIC_AVAILABLE = True
except Exception:
    mic_recorder = None  # type: ignore
    MIC_AVAILABLE = False

# --- AI PARSER ---
from core.ai_parser import parse_transaction_with_gemini

# --- DB OPS ---
from core.db_operations import (
    load_data_db,
    add_record_db,
    execute_query_db,
    normalize_date_to_iso,
    normalize_type,
    ensure_category_exists,
    ensure_payee_exists,
    get_category_type,
)

# --- OPTIONAL LOCAL WHISPER SUPPORT (SAFE / LAZY) ---
try:
    import faster_whisper  # noqa: F401
    WHISPER_AVAILABLE = True
except Exception:
    WHISPER_AVAILABLE = False


# ============================================================
# 🔐 USER CONTEXT
# ============================================================
def _get_user_id() -> str:
    """
    Your auth layer should set st.session_state["username"].
    If it's missing, we fall back to "default".
    """
    uid = st.session_state.get("username")
    uid = str(uid).strip() if uid is not None else ""
    return uid or "default"


# ============================================================
# 🎙️ WHISPER (OPTIONAL)
# ============================================================
@st.cache_resource(show_spinner=False)
def _get_whisper_model():
    if not WHISPER_AVAILABLE:
        return None
    try:
        from faster_whisper import WhisperModel  # local import
    except Exception:
        return None
    return WhisperModel("small", device="cpu", compute_type="int8")


def transcribe_mic_audio(audio: dict) -> str:
    try:
        if not isinstance(audio, dict):
            return ""
        if not WHISPER_AVAILABLE:
            return ""

        b = audio.get("bytes")
        if not b:
            return ""

        if isinstance(b, str):
            s = b.strip()
            if s.startswith(("b'", 'b"')):
                try:
                    b = ast.literal_eval(s)
                except Exception:
                    return ""
            else:
                return ""

        if not isinstance(b, (bytes, bytearray)):
            return ""

        fmt = (audio.get("format") or "webm").lower().strip(".")
        suffix = f".{fmt}" if fmt else ".webm"

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                f.write(b)
                tmp_path = f.name

            model = _get_whisper_model()
            if model is None:
                return ""

            segments, _info = model.transcribe(tmp_path, beam_size=5, vad_filter=True)
            return " ".join((seg.text or "").strip() for seg in segments).strip()

        finally:
            try:
                if tmp_path and Path(tmp_path).exists():
                    Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    except Exception as e:
        st.warning(f"Whisper transcription failed: {e}")
        return ""


# ============================================================
# 🧭 PAGE ROUTING GUARD
# ============================================================
def _force_transactions_page():
    for k in ("page", "active_page", "current_page", "nav_page", "selected_page", "menu", "active_tab"):
        if k in st.session_state:
            v = str(st.session_state.get(k, "")).strip().lower()
            if v == "" or ("data" in v and "manage" in v):
                st.session_state[k] = "Transactions"


# ============================================================
# 🧮 SHARED MATH LOGIC
# ============================================================
def _get_signed_amount(row) -> float:
    try:
        amt = float(row.get("amount", 0) or 0)
    except Exception:
        amt = 0.0

    t = str(row.get("type", "")).strip().lower()
    if t in ["income", "opening balance", "deposit", "refund"]:
        return amt
    if t in ["expense", "transfer", "withdrawal", "payment"]:
        return -abs(amt)
    return 0.0


def _upsert_settlement_transfer(selected_account: str, amount_val: float, date_val: str | date):
    """
    Credit card auto-settlement. USER-SCOPED.
    Uses named params (SQLAlchemy text()) to work on PostgreSQL and SQLite.
    """
    user_id = _get_user_id()

    acc_df = load_data_db("accounts", user_id=user_id)
    if acc_df is None or acc_df.empty or selected_account not in acc_df["name"].astype(str).values:
        return

    this_acc = acc_df[acc_df["name"].astype(str) == str(selected_account)].iloc[0]
    if str(this_acc.get("account_type", "")).strip() != "Credit Card":
        return

    trans_date = pd.to_datetime(date_val, errors="coerce")
    if pd.isna(trans_date):
        return

    due_day = int(this_acc.get("credit_due_day", 20) or 20)
    settlement_date = (trans_date + relativedelta(months=1)).replace(day=due_day).strftime("%Y-%m-%d")
    source_account = this_acc.get("credit_source_account") or "Brukskonto"

    tx_df = load_data_db("transactions", user_id=user_id)
    if tx_df is None or tx_df.empty:
        return

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

    # if already exists (for that user/date/account), update it
    existing_mask = (
        (tx_df.get("user_id", "").astype(str) == str(user_id))
        & (tx_df.get("date").astype(str) == str(settlement_date))
        & (tx_df.get("account").astype(str) == str(selected_account))
        & (tx_df.get("category", "").astype(str) == "Transfer")
        & (tx_df.get("description", "").astype(str).str.contains("Auto-settle", na=False))
    )

    if not tx_df.loc[existing_mask].empty:
        update_sql = """
            UPDATE transactions
               SET amount = :amt
             WHERE user_id = :uid
               AND date = :dt
               AND account = :acc
               AND description LIKE '%Auto-settle%'
        """
        execute_query_db(update_sql, {"amt": float(target_transfer_amount), "uid": user_id, "dt": settlement_date, "acc": selected_account})
        return

    # otherwise insert pair
    out_transfer = {
        "user_id": user_id,
        "date": settlement_date,
        "amount": float(target_transfer_amount),
        "type": "expense",
        "account": str(source_account),
        "category": "Transfer",
        "payee": f"Settlement: {selected_account}",
        "description": f"Auto-settle for {selected_account}",
    }
    in_transfer = out_transfer.copy()
    in_transfer["type"] = "income"
    in_transfer["account"] = str(selected_account)
    in_transfer["payee"] = f"From {source_account}"

    add_record_db("transactions", out_transfer)
    add_record_db("transactions", in_transfer)


# ============================================================
# ✨ AI SMART ENTRY COMPONENT
# ============================================================
def render_ai_smart_entry(selected_account: str):
    st.markdown(
        """
        <div class="ziva-sidebar-card">
            <h4 style="margin: 0; color: #2c3e50; font-size: 14px; font-weight: bold;">✨ AI Smart Entry</h4>
            <p style="margin: 0 0 8px 0; color: #666; font-size: 11px;">"Lunch 150 at McDonalds" or use mic 🎙️</p>
        </div>
        """,
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

    query = st.text_area(
        "AI Input",
        value=st.session_state.get("voice_transcript", ""),
        placeholder='e.g. "Spent 250 NOK on groceries"',
        height=70,
        label_visibility="collapsed",
        key="ai_entry_widget",
    )
    st.session_state["voice_transcript"] = query

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🧹 Clear", use_container_width=True, key="ai_entry_clear"):
            st.session_state["voice_transcript"] = ""
            st.session_state["ai_entry_widget"] = ""
            st.rerun()

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
                "user_id": user_id,
                "date": normalize_date_to_iso(data.get("date")),
                "type": normalize_type(data.get("type", "expense")),
                "account": selected_account,
                "category": data.get("category", "Uncategorized"),
                "payee": data.get("payee", "Unknown"),
                "amount": float(data.get("amount", 0) or 0),
                "description": data.get("description", "AI Entry"),
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
# CACHING & DATA
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
def _load_categories() -> list[str]:
    user_id = _get_user_id()
    cat = load_data_db("categories", user_id=user_id)
    return sorted(cat["name"].dropna().astype(str).unique().tolist()) if cat is not None and not cat.empty else []


@st.cache_data(ttl=30)
def _load_payees() -> list[str]:
    user_id = _get_user_id()
    try:
        pay = load_data_db("payees", user_id=user_id)
        if pay is not None and not pay.empty:
            return sorted(pay["name"].dropna().astype(str).unique().tolist())
        tx = load_data_db("transactions", user_id=user_id)
        if tx is not None and not tx.empty:
            return sorted(tx["payee"].dropna().astype(str).unique().tolist())
        return []
    except Exception:
        return []


def _invalidate_cache():
    st.session_state["tx_data_version"] = int(st.session_state.get("tx_data_version", 0)) + 1
    _load_transactions.clear()
    _load_accounts.clear()
    _load_categories.clear()
    _load_payees.clear()


def _compute_account_balances(df_all: pd.DataFrame) -> dict[str, float]:
    if df_all is None or df_all.empty:
        return {}
    df = df_all.copy()
    df["date_dt"] = pd.to_datetime(df.get("date"), errors="coerce").dt.date
    df = df[df["date_dt"] <= date.today()]
    df["signed"] = df.apply(_get_signed_amount, axis=1)
    return df.groupby("account")["signed"].sum().to_dict()


def _with_money_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["signed_amount"] = out.apply(_get_signed_amount, axis=1)
    out["Out"] = out["signed_amount"].apply(lambda x: x if x < 0 else 0.0)
    out["In"] = out["signed_amount"].apply(lambda x: x if x > 0 else 0.0)
    out = out.sort_values(by="date", ascending=True)
    out["Balance"] = out["signed_amount"].cumsum()
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

        def _set_payee(name: str):
            st.session_state["tx_payee_smart"] = name

        payee_val = st.text_input(
            "Payee (Type to search or add new)",
            value=st.session_state["tx_payee_smart"],
            key="payee_input_widget",
            placeholder="e.g. Kiwi",
        ).strip()

        if payee_val != st.session_state["tx_payee_smart"]:
            st.session_state["tx_payee_smart"] = payee_val

        if payee_val:
            matches = [p for p in all_payees if payee_val.lower() in p.lower()]
            matches = [m for m in matches if m.lower() != payee_val.lower()]
            if matches:
                st.caption("Suggestions:")
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
            if not payee_val:
                st.error("Please enter a Payee.")
                return
            if amount_val is None or float(amount_val) == 0:
                st.error("Please enter an Amount.")
                return
            if category_val == "➕ Add New..." and not new_cat_name.strip():
                st.error("Please enter a name for the new category.")
                return

            actual_cat = new_cat_name.strip() if category_val == "➕ Add New..." else category_val
            actual_cat = actual_cat.strip()

            # Ensure category/payee exist for this user
            ensure_payee_exists(payee_val, user_id)
            ensure_category_exists(actual_cat, final_type, user_id)

            new_record = {
                "user_id": user_id,
                "date": normalize_date_to_iso(date_val),
                "amount": float(amount_val),
                "type": final_type,
                "payee": payee_val,
                "category": actual_cat,
                "description": desc_val,
                "account": selected_account,
            }

            add_record_db("transactions", new_record)
            _upsert_settlement_transfer(selected_account, float(amount_val), date_val)

            st.success(f"Saved: {payee_val} - {amount_val}")
            st.session_state["tx_payee_smart"] = ""
            _invalidate_cache()
            time.sleep(0.2)
            st.rerun()

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
                if not r_payee or float(r_amt) == 0:
                    st.error("Missing Payee or Amount")
                    return
                if not r_cat:
                    st.error("Missing Category")
                    return

                rec_type = normalize_type(get_category_type(r_cat, user_id) or "expense")
                ensure_payee_exists(r_payee, user_id)

                current_d = r_start_date
                for i in range(int(r_count)):
                    if i > 0:
                        if r_freq == "Monthly":
                            current_d += relativedelta(months=1)
                        elif r_freq == "Weekly":
                            current_d += timedelta(weeks=1)
                        elif r_freq == "Yearly":
                            current_d += relativedelta(years=1)

                    add_record_db(
                        "transactions",
                        {
                            "user_id": user_id,
                            "date": normalize_date_to_iso(current_d),
                            "amount": float(r_amt),
                            "type": rec_type,
                            "payee": r_payee,
                            "category": r_cat,
                            "description": f"Rec ({i+1}/{r_count})",
                            "account": selected_account,
                        },
                    )
                    _upsert_settlement_transfer(selected_account, float(r_amt), current_d)

                _invalidate_cache()
                st.success(f"Generated {r_count} transactions!")
                st.rerun()


@st.dialog("New Transfer", width="large")
def _dialog_add_transfer(selected_account: str):
    user_id = _get_user_id()
    accounts = _load_accounts()
    if len(accounts) < 2:
        st.warning("⚠️ Need at least 2 accounts.")
        return

    with st.form("tx_transfer_standalone"):
        t_c1, t_c2 = st.columns(2)
        curr_idx = accounts.index(selected_account) if selected_account in accounts else 0
        t_from = t_c1.selectbox("From Account", options=accounts, index=curr_idx)
        t_to = t_c2.selectbox("To Account", options=accounts, index=0 if curr_idx != 0 else 1)
        t_amt = st.number_input("Amount", min_value=0.0, format="%.2f", step=100.0)
        t_desc = st.text_input("Note", "Internal Transfer")
        t_date = st.date_input("Date", value=date.today())

        if st.form_submit_button("💸 Execute Transfer", use_container_width=True, type="primary"):
            if t_from == t_to:
                st.error("From and To cannot be the same.")
                return
            if float(t_amt) <= 0:
                st.error("Amount must be > 0.")
                return

            base = {
                "user_id": user_id,
                "date": normalize_date_to_iso(t_date),
                "amount": float(t_amt),
                "category": "Transfer",
                "description": t_desc,
            }
            add_record_db("transactions", {**base, "type": "expense", "payee": f"To {t_to}", "account": t_from})
            add_record_db("transactions", {**base, "type": "income", "payee": f"From {t_from}", "account": t_to})

            _invalidate_cache()
            st.rerun()


# ============================================================
# MAIN PAGE
# ============================================================
def render_transactions_page():
    _force_transactions_page()

    st.session_state.setdefault("tx_data_version", 0)
    df_all = _load_transactions(st.session_state["tx_data_version"])

    user_id = _get_user_id()
    accounts_df = load_data_db("accounts", user_id=user_id)
    accounts = sorted(accounts_df["name"].dropna().astype(str).tolist()) if accounts_df is not None and not accounts_df.empty else []

    left_col, right_col = st.columns([1, 4], gap="large")

    with left_col:
        try:
            st.image("assets/icons/ziva_icon.png", width=80)
        except Exception:
            pass

        st.markdown("### Accounts")

        if not accounts:
            st.info("No accounts found.")
            selected_account = "Default"
        else:
            st.session_state.setdefault("tx_selected_account", accounts[0])
            if st.session_state["tx_selected_account"] not in accounts:
                st.session_state["tx_selected_account"] = accounts[0]

            for acc in accounts:
                is_active = st.session_state["tx_selected_account"] == acc
                if st.button(
                    f"🏦 {acc}",
                    key=f"btn_{acc}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state["tx_selected_account"] = acc
                    st.rerun()

            selected_account = st.session_state["tx_selected_account"]

        st.markdown("---")
        render_ai_smart_entry(selected_account)

    with right_col:
        h1, h2, h3 = st.columns([2, 1, 1])
        with h1:
            st.markdown(f"## {selected_account}")
            st.caption("Detailed transaction history and AI insights.")

        with h2:
            if st.button("➕ New Record", use_container_width=True, type="primary"):
                _dialog_add_transaction(selected_account)

        with h3:
            if st.button("⇄ Transfer", use_container_width=True):
                _dialog_add_transfer(selected_account)

        df_acc = (
            df_all[df_all["account"].astype(str) == str(selected_account)].copy()
            if df_all is not None and not df_all.empty
            else pd.DataFrame()
        )

        if df_acc.empty:
            st.info("No transactions for this account.")
            return

        df_view = _with_money_columns(df_acc)
        display_df = df_view[["date", "category", "payee", "Out", "In", "Balance"]].copy()

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DatetimeColumn("Date", format="DD.MM.YYYY HH:mm"),
                "Out": st.column_config.NumberColumn("Expense", format="%.2f kr"),
                "In": st.column_config.NumberColumn("Income", format="%.2f kr"),
                "Balance": st.column_config.NumberColumn("Running Balance", format="%.2f kr"),
            },
        )
