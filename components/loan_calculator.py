# components/loan_calculator.py
import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
from dateutil.relativedelta import relativedelta

import plotly.express as px
import plotly.graph_objects as go

from core.db_operations import add_record_db, load_data_db, execute_query_db

# ============================================================
# 🔐 HELPER
# ============================================================
def _get_user_id_loan() -> str:
    """Consistent user ID fetcher"""
    uid = st.session_state.get("username")
    uid = str(uid).strip() if uid is not None else ""
    return uid or "default"

def _sanitize_record(record):
    """
    Recursively convert all numpy types to python native types
    to prevent SQLAlchemy/psycopg2 errors.
    """
    new_record = {}
    for k, v in record.items():
        if isinstance(v, (np.integer, np.int64, np.int32)):
            new_record[k] = int(v)
        elif isinstance(v, (np.floating, np.float64, np.float32)):
            new_record[k] = float(v)
        elif isinstance(v, np.ndarray):
            new_record[k] = v.tolist()
        else:
            new_record[k] = v
    return new_record

# ============================================================
# 🧱 DB MIGRATIONS
# ============================================================
def _ensure_loans_schema():
    execute_query_db("""
    CREATE TABLE IF NOT EXISTS loans (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255),
        balance NUMERIC,
        interest_rate NUMERIC,
        min_payment NUMERIC,
        user_id VARCHAR(255)
    );
    """)
    cols = [
        ("admin_fee", "NUMERIC DEFAULT 0"),
        ("payment_day", "INTEGER DEFAULT 1"),
        ("pay_from_account", "VARCHAR(255)"),
        ("start_date", "DATE"),
        ("term_years", "INTEGER"),
        ("target_date", "DATE"),
        ("calculation_mode", "VARCHAR(50)"),
        ("interest_only_from", "DATE"),
        ("interest_only_to", "DATE"),
        ("loan_type", "VARCHAR(50) DEFAULT 'Annuity'"),
        ("created_at", "TIMESTAMPTZ DEFAULT now()")
    ]
    for col, dtype in cols:
        execute_query_db(f"ALTER TABLE loans ADD COLUMN IF NOT EXISTS {col} {dtype};")

    execute_query_db("""
    CREATE TABLE IF NOT EXISTS loan_extra_payments (
        id SERIAL PRIMARY KEY,
        loan_id INTEGER,
        pay_date DATE,
        amount NUMERIC,
        note VARCHAR(255),
        user_id VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """)
    
    execute_query_db("""
    CREATE TABLE IF NOT EXISTS loan_terms_history (
        id SERIAL PRIMARY KEY,
        loan_id INTEGER,
        change_date DATE,
        interest_rate NUMERIC,
        admin_fee NUMERIC,
        note VARCHAR(255),
        user_id VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """)

# ============================================================
# 🔄 DATA FETCHING
# ============================================================
@st.cache_data(ttl=5)
def _load_loans_cached(user_id: str, version: int) -> pd.DataFrame:
    df = load_data_db("loans")
    if df is not None and not df.empty:
        if 'user_id' in df.columns:
             return df[df['user_id'].astype(str) == str(user_id)]
    return pd.DataFrame()

def _load_adjustments(loan_id: int) -> pd.DataFrame:
    """Fetch extra payments/adjustments."""
    df = load_data_db("loan_extra_payments")
    if df is None or df.empty:
        return pd.DataFrame(columns=["id", "loan_id", "pay_date", "amount", "note"])
    
    if 'loan_id' in df.columns:
        df_filtered = df[df['loan_id'].astype(str) == str(loan_id)].copy()
    else:
        return pd.DataFrame(columns=["id", "loan_id", "pay_date", "amount", "note"])
        
    if df_filtered.empty:
        return pd.DataFrame(columns=["id", "loan_id", "pay_date", "amount", "note"])

    if 'pay_date' in df_filtered.columns:
        df_filtered['pay_date'] = pd.to_datetime(df_filtered['pay_date'])
        df_filtered = df_filtered.sort_values(by="pay_date")
        
    return df_filtered

def _load_terms_history(loan_id: int) -> pd.DataFrame:
    """Fetch interest rate/fee changes."""
    df = load_data_db("loan_terms_history")
    if df is None or df.empty:
        return pd.DataFrame(columns=["id", "loan_id", "change_date", "interest_rate", "admin_fee", "note"])
    
    if 'loan_id' in df.columns:
        df_filtered = df[df['loan_id'].astype(str) == str(loan_id)].copy()
    else:
        return pd.DataFrame(columns=["id", "loan_id", "change_date", "interest_rate", "admin_fee", "note"])
        
    if df_filtered.empty:
        return pd.DataFrame(columns=["id", "loan_id", "change_date", "interest_rate", "admin_fee", "note"])

    if 'change_date' in df_filtered.columns:
        df_filtered['change_date'] = pd.to_datetime(df_filtered['change_date'])
        df_filtered = df_filtered.sort_values(by="change_date")
        
    return df_filtered

# ============================================================
# 🧮 MATH HELPERS
# ============================================================
def _add_months(start_date, months):
    return start_date + relativedelta(months=+months)

def _count_months(start_date, end_date):
    diff = relativedelta(end_date, start_date)
    return diff.years * 12 + diff.months

def _calculate_annuity_payment(principal, annual_rate, months):
    if months <= 0: return principal
    if annual_rate <= 0: return principal / months
    r = (annual_rate / 100.0) / 12.0
    numerator = r * principal
    denominator = 1 - (1 + r)**(-months)
    return numerator / denominator

def _generate_schedule(
    balance, rate, start_date, payment_day, mode, 
    loan_type="Annuity", 
    target_payment=None, target_date=None, admin_fee=0, 
    extra_payments_df=None, terms_history_df=None,
    io_from=None, io_to=None
):
    schedule = []
    current_balance = float(balance)
    
    current_rate = float(rate)
    current_fee = float(admin_fee)
    
    # Process extras
    extras = {}
    if extra_payments_df is not None and not extra_payments_df.empty:
        if not pd.api.types.is_datetime64_any_dtype(extra_payments_df['pay_date']):
            extra_payments_df['pay_date'] = pd.to_datetime(extra_payments_df['pay_date'])
        for _, row in extra_payments_df.iterrows():
            d = row['pay_date'].date()
            key = (d.year, d.month)
            extras[key] = extras.get(key, 0.0) + float(row['amount'])

    # Process terms history
    terms_changes = []
    if terms_history_df is not None and not terms_history_df.empty:
        if not pd.api.types.is_datetime64_any_dtype(terms_history_df['change_date']):
            terms_history_df['change_date'] = pd.to_datetime(terms_history_df['change_date'])
        for _, row in terms_history_df.iterrows():
            terms_changes.append({
                'date': row['change_date'].date(),
                'rate': float(row['interest_rate']),
                'fee': float(row['admin_fee'])
            })
        terms_changes.sort(key=lambda x: x['date'])

    current_date = start_date
    if current_date.day > payment_day:
         current_date = _add_months(current_date, 1)
    current_date = current_date.replace(day=payment_day)

    max_months = 720 # 60 years cap
    
    fixed_principal_amount = 0.0
    annuity_payment_amount = 0.0
    
    def recalculate_payment(curr_bal, curr_rate, calc_date):
        if mode == 'date' and target_date:
            rem_months = max(1, _count_months(calc_date, target_date))
            if loan_type == "Serial":
                return curr_bal / rem_months
            elif loan_type == "Frame":
                return 0.0
            else:
                return _calculate_annuity_payment(curr_bal, curr_rate, rem_months)
        else:
             return float(target_payment)

    base_payment_val = recalculate_payment(current_balance, current_rate, start_date)
    if loan_type == "Serial": fixed_principal_amount = base_payment_val
    elif loan_type == "Annuity": annuity_payment_amount = base_payment_val
    elif loan_type == "Frame": fixed_principal_amount = 0.0

    month_idx = 1
    
    while current_balance > 1.0 and month_idx <= max_months:
        
        # 1. Update Terms
        active_terms = None
        for chg in terms_changes:
            if chg['date'] <= current_date:
                active_terms = chg
            else:
                break
        
        new_rate = active_terms['rate'] if active_terms else float(rate)
        new_fee = active_terms['fee'] if active_terms else float(admin_fee)
        
        terms_changed = (abs(new_rate - current_rate) > 0.001)
        
        current_rate = new_rate
        current_fee = new_fee
        monthly_rate = (current_rate / 100.0) / 12.0
        
        # 2. Recalculate Payment
        if terms_changed and mode == 'date' and loan_type != "Frame":
            base_payment_val = recalculate_payment(current_balance, current_rate, current_date)
            if loan_type == "Serial": fixed_principal_amount = base_payment_val
            elif loan_type == "Annuity": annuity_payment_amount = base_payment_val

        # 3. Compute Interest
        interest = current_balance * monthly_rate
        
        # 4. Payment
        is_io = False
        if io_from and io_to and io_from <= current_date <= io_to: is_io = True
        if loan_type == "Frame": is_io = True 

        principal_payment = 0.0
        required_payment = 0.0
        
        if is_io:
            principal_payment = 0.0
            required_payment = interest
        else:
            if loan_type == "Serial":
                principal_payment = fixed_principal_amount
                required_payment = principal_payment + interest
            else:
                base = annuity_payment_amount
                if base < interest: base = interest 
                principal_payment = base - interest
                required_payment = base

        if principal_payment > current_balance:
            principal_payment = current_balance
            required_payment = interest + principal_payment

        extra_amt = extras.get((current_date.year, current_date.month), 0.0)
        real_principal = principal_payment + extra_amt
        total_deduction = required_payment + current_fee + extra_amt

        if real_principal > current_balance:
            excess = real_principal - current_balance
            real_principal = current_balance
            total_deduction -= excess 

        end_balance = current_balance - real_principal
        
        status_label = "Payment"
        if is_io: status_label = "Interest Only"
        if loan_type == "Frame" and extra_amt > 0: status_label = "Extra Payment"

        schedule.append({
            "Month": month_idx, "Date": current_date,
            "Start Balance": current_balance, "Interest": interest,
            "Rate %": current_rate, "Fee": current_fee,
            "Principal": principal_payment, "Extra / Adj": extra_amt,
            "Admin Fee": current_fee, "Total Payment": total_deduction,
            "End Balance": max(0, end_balance),
            "Status": status_label
        })
        current_balance = end_balance
        current_date = _add_months(current_date, 1)
        month_idx += 1

    return pd.DataFrame(schedule)

# ============================================================
# 🟢 DIALOGS
# ============================================================
@st.dialog("⚖️ Balance Adjustments")
def _dialog_manage_adjustments(loan_id, loan_name):
    st.markdown(f"### Adjustments for **{loan_name}**")
    st.info("Add extra payments (reduce balance) or corrections.")
    user_id = _get_user_id_loan()
    
    with st.form("add_adj_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 3])
        d_date = c1.date_input("Date", value=dt.date.today())
        d_amt = c2.number_input("Amount (NOK)", step=1000.0, help="Positive to PAY DOWN")
        d_note = c3.text_input("Note", placeholder="Bonus, Inheritance...")
        if st.form_submit_button("➕ Add Adjustment"):
            add_record_db("loan_extra_payments", {
                "loan_id": int(loan_id), "pay_date": d_date.isoformat(),
                "amount": float(d_amt), "note": d_note, "user_id": user_id
            })
            st.success("Added!"); st.session_state["loan_data_version"] += 1; st.rerun()

    df_adj = _load_adjustments(loan_id)
    if not df_adj.empty:
        st.markdown("#### History")
        for i, row in df_adj.iterrows():
            c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
            c1.write(row['pay_date'].date())
            c2.write(f"**{row['amount']:,.0f}**")
            c3.write(row['note'])
            if c4.button("🗑️", key=f"d_adj_{row['id']}"):
                execute_query_db("DELETE FROM loan_extra_payments WHERE id = :id", {"id": row['id']})
                st.session_state["loan_data_version"] += 1; st.rerun()
    else: st.caption("No adjustments.")

@st.dialog("📉 Terms & Rates")
def _dialog_manage_terms(loan_id, loan_name, current_rate, current_fee):
    st.markdown(f"### Terms History for **{loan_name}**")
    st.info("Log changes to interest rates or fees.")
    user_id = _get_user_id_loan()
    
    with st.form("add_terms_form", clear_on_submit=True):
        st.write("**New Terms**")
        c1, c2, c3 = st.columns([2, 1, 1])
        t_date = c1.date_input("Effective From", value=dt.date.today())
        t_rate = c2.number_input("New Rate (%)", value=float(current_rate), step=0.1, format="%.2f")
        t_fee = c3.number_input("New Fee (NOK)", value=float(current_fee), step=5.0)
        t_note = st.text_input("Note", placeholder="Norges Bank hike...")
        
        if st.form_submit_button("💾 Save New Terms"):
            add_record_db("loan_terms_history", {
                "loan_id": int(loan_id), "change_date": t_date.isoformat(),
                "interest_rate": float(t_rate), "admin_fee": float(t_fee),
                "note": t_note, "user_id": user_id
            })
            st.success("Terms Updated!"); st.session_state["loan_data_version"] += 1; st.rerun()

    df_terms = _load_terms_history(loan_id)
    if not df_terms.empty:
        st.markdown("#### Rate History")
        for i, row in df_terms.iterrows():
            c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
            c1.write(f"📅 {row['change_date'].date()}")
            c2.write(f"**{row['interest_rate']}%** / {row['admin_fee']}kr")
            c3.write(row['note'])
            if c4.button("🗑️", key=f"d_term_{row['id']}"):
                execute_query_db("DELETE FROM loan_terms_history WHERE id = :id", {"id": row['id']})
                st.session_state["loan_data_version"] += 1; st.rerun()
    else: st.caption("No historical changes logged.")

@st.dialog("📝 Generate Loan Transactions")
def _dialog_generate_transactions(loan_data):
    st.write(f"Generate payments for **{loan_data['name']}**")
    
    col1, col2 = st.columns(2)
    months_to_gen = col1.number_input("Months", min_value=1, max_value=36, value=6, key=f"dlg_months_{loan_data['id']}")
    start_date_gen = col2.date_input("Start Date", value=dt.date.today(), key=f"dlg_start_{loan_data['id']}")
    init_balance = st.checkbox("Initialize Opening Balance?", value=False, key=f"dlg_init_{loan_data['id']}")
    
    if st.button("🚀 Execute", type="primary", use_container_width=True, key=f"dlg_btn_exec_{loan_data['id']}"):
        user_id = _get_user_id_loan()
        extras_df = _load_adjustments(loan_data['id'])
        terms_df = _load_terms_history(loan_data['id'])

        df_sched = _generate_schedule(
            balance=loan_data['balance'], rate=loan_data['interest_rate'],
            start_date=start_date_gen, payment_day=int(loan_data.get('payment_day', 1)),
            mode=loan_data['calculation_mode'], loan_type=loan_data.get('loan_type', 'Annuity'),
            target_payment=loan_data['min_payment'],
            target_date=pd.to_datetime(loan_data['target_date']).date() if loan_data['target_date'] else None,
            admin_fee=float(loan_data.get('admin_fee', 0)),
            io_from=pd.to_datetime(loan_data['interest_only_from']).date() if loan_data['interest_only_from'] else None,
            io_to=pd.to_datetime(loan_data['interest_only_to']).date() if loan_data['interest_only_to'] else None,
            extra_payments_df=extras_df, terms_history_df=terms_df
        )
        
        if df_sched.empty: st.error("Calc error."); return

        df_to_process = df_sched.head(months_to_gen)
        count = 0
        
        if init_balance:
            add_record_db("transactions", _sanitize_record({
                "user_id": user_id, "date": start_date_gen.strftime("%Y-%m-%d"),
                "amount": -float(loan_data['balance']), "type": "opening balance",
                "account": loan_data['name'], "category": "Opening Balance",
                "payee": "System", "description": "Initial Loan Balance"
            }))

        for _, row in df_to_process.iterrows():
            pay_date = row['Date'].isoformat()
            total_pay = float(row['Total Payment'])
            principal = float(row['Principal'])
            interest = float(row['Interest'])
            fee = float(row['Admin Fee'])
            
            if interest > 0:
                add_record_db("transactions", _sanitize_record({
                    "user_id": user_id, "date": pay_date, "amount": -interest, "type": "expense",
                    "account": loan_data['pay_from_account'], "category": "Loan Interest",
                    "payee": loan_data['name'], "description": f"Loan Interest ({row['Rate %']}%)"
                }))
            
            if fee > 0:
                 add_record_db("transactions", _sanitize_record({
                    "user_id": user_id, "date": pay_date, "amount": -fee, "type": "expense",
                    "account": loan_data['pay_from_account'], "category": "Loan Fees",
                    "payee": loan_data['name'], "description": "Loan Fee"
                }))

            reduction_amt = principal + float(row['Extra / Adj'])
            if reduction_amt > 0:
                add_record_db("transactions", _sanitize_record({
                    "user_id": user_id, "date": pay_date, "amount": -reduction_amt, "type": "expense",
                    "account": loan_data['pay_from_account'], "category": "Loan Repayment",
                    "payee": f"To {loan_data['name']}", "description": "Principal Payment"
                }))
                add_record_db("transactions", _sanitize_record({
                    "user_id": user_id, "date": pay_date, "amount": reduction_amt, "type": "income", 
                    "account": loan_data['name'], "category": "Principal Reduction",
                    "payee": f"From {loan_data['pay_from_account']}", "description": "Principal Payment"
                }))
            count += 1
            
        st.success(f"✅ Created {count} month(s) of transactions!"); st.rerun()

# ============================================================
# 🎨 UI COMPONENT
# ============================================================
def render_loan_calculator():
    _ensure_loans_schema()
    user_id = _get_user_id_loan()
    
    st.markdown("## 🏦 Advanced Loan Planner")
    
    st.session_state.setdefault("loan_data_version", 0)
    my_loans = _load_loans_cached(user_id, st.session_state["loan_data_version"])
    
    tab_saved, tab_calc = st.tabs(["📂 Your Saved Loans", "➕ Create New Plan"])
    
    with tab_saved:
        if my_loans.empty: st.info("No saved loans yet.")
        else:
            for _, loan in my_loans.iterrows():
                extras_df = _load_adjustments(loan['id'])
                terms_df = _load_terms_history(loan['id'])
                l_type = loan.get('loan_type', 'Annuity')
                
                df_preview = _generate_schedule(
                    balance=loan['balance'], rate=loan['interest_rate'],
                    start_date=pd.to_datetime(loan['start_date']).date(),
                    payment_day=int(loan['payment_day']),
                    mode=loan['calculation_mode'], loan_type=l_type,
                    target_payment=loan['min_payment'],
                    target_date=pd.to_datetime(loan['target_date']).date() if loan['target_date'] else None,
                    admin_fee=float(loan.get('admin_fee', 0)),
                    io_from=pd.to_datetime(loan['interest_only_from']).date() if loan['interest_only_from'] else None,
                    io_to=pd.to_datetime(loan['interest_only_to']).date() if loan['interest_only_to'] else None,
                    extra_payments_df=extras_df, terms_history_df=terms_df
                )
                
                payoff_str = "Never"
                if not df_preview.empty:
                    last_bal = df_preview.iloc[-1]['End Balance']
                    if last_bal <= 1.0:
                        payoff_str = df_preview.iloc[-1]['Date'].strftime("%b %Y")

                with st.expander(f"💳 {loan['name']} ({l_type}) - Bal: {float(loan['balance']):,.0f} - Payoff: {payoff_str}"):
                    c1, c2, c3 = st.columns([1, 1, 1])
                    with c1:
                        st.write(f"**Base Rate:** {loan['interest_rate']}%")
                        st.write(f"**Account:** {loan['pay_from_account']}")
                    with c2:
                        st.write(f"**Base Fee:** {loan['admin_fee']} kr")
                        mode_lbl = "Target Date" if loan.get('calculation_mode') == 'date' else "Fixed Payment"
                        st.write(f"**Mode:** {mode_lbl}")
                    with c3:
                        b1, b2 = st.columns(2)
                        if b1.button("📉 Terms", key=f"trm_{loan['id']}", use_container_width=True):
                            _dialog_manage_terms(loan['id'], loan['name'], loan['interest_rate'], loan.get('admin_fee',0))
                        if b2.button("⚖️ Adjust", key=f"adj_{loan['id']}", use_container_width=True):
                            _dialog_manage_adjustments(loan['id'], loan['name'])
                            
                        b3, b4 = st.columns(2)
                        if b3.button("📝 Gen Tx", key=f"exec_{loan['id']}", use_container_width=True):
                            _dialog_generate_transactions(loan)
                        if b4.button("🗑️ Delete", key=f"del_{loan['id']}", use_container_width=True):
                            execute_query_db(f"DELETE FROM loans WHERE id={loan['id']}")
                            execute_query_db(f"DELETE FROM loan_extra_payments WHERE loan_id={loan['id']}")
                            execute_query_db(f"DELETE FROM loan_terms_history WHERE loan_id={loan['id']}")
                            st.session_state["loan_data_version"] += 1; st.rerun()
                    
                    if not df_preview.empty:
                        has_rate_changes = len(df_preview['Rate %'].unique()) > 1
                        title_g = "Projected Balance (Rate Changes Applied)" if has_rate_changes else "Projected Balance"
                        fig_mini = px.line(df_preview, x='Date', y='End Balance', title=title_g)
                        fig_mini.update_layout(height=250, margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_mini, use_container_width=True)

    with tab_calc:
        accounts_df = load_data_db("accounts", user_id=user_id)
        account_options = ["Brukskonto", "Regningskonto", "Lønnskonto"]
        if accounts_df is not None and not accounts_df.empty:
            if 'name' in accounts_df.columns:
                account_options = accounts_df['name'].tolist() + account_options
        account_options = list(set(account_options))

        with st.form("loan_calculator_form"):
            st.caption("Plan your loan based on monthly budget OR a target payoff date.")
            c1, c2, c3 = st.columns(3)
            with c1:
                f_name = st.text_input("Loan Name", value="Huslån")
                f_balance = st.number_input("Current Balance", value=2500000.0, step=10000.0, format="%.2f")
            with c2:
                f_rate = st.number_input("Interest Rate (%)", value=5.49, step=0.1, format="%.2f")
                f_type = st.selectbox("Loan Type", ["Annuity", "Serial", "Frame"], index=0)
            with c3:
                f_pay_from = st.selectbox("Pay from Account", options=account_options)
                f_fee = st.number_input("Monthly Fee (NOK)", value=50.0, step=5.0)
                f_pay_day = st.number_input("Payment Day", min_value=1, max_value=28, value=20)

            st.markdown("---")
            st.subheader("Payment Strategy")
            f_mode = st.radio("Calculation Mode", ["🎯 Target Date (Calculate Payment)", "💵 Fixed Amount (Calculate Date)"], horizontal=True)
            
            s1, s2 = st.columns(2)
            with s1: f_start_date = st.date_input("Start Date", value=dt.date.today())
            with s2:
                calc_target_date = dt.date.today() + relativedelta(years=25)
                f_monthly_pay = 15000.0
                if "Target Date" in f_mode: f_target_date = st.date_input("Payoff Goal Date", value=calc_target_date)
                else: 
                    lbl = "Fixed Principal" if f_type == "Serial" else "Total Monthly Payment"
                    f_monthly_pay = st.number_input(f"{lbl} (NOK)", value=f_monthly_pay, step=500.0)
                    f_target_date = None

            f_io_enable, f_io_start, f_io_end = False, None, None
            if f_type != "Frame":
                with st.expander("Optional: Interest Only Period"):
                    c_io1, c_io2, c_io3 = st.columns(3)
                    f_io_enable = c_io1.checkbox("Enable Interest-Only?")
                    f_io_start = c_io2.date_input("IO From", value=dt.date.today())
                    f_io_end = c_io3.date_input("IO To", value=dt.date.today() + relativedelta(years=1))

            submitted = st.form_submit_button("🚀 Calculate Plan", type="primary", use_container_width=True)

        if submitted:
            target_mode = "date" if "Target" in f_mode else "payment"
            df = _generate_schedule(
                balance=f_balance, rate=f_rate, start_date=f_start_date, payment_day=f_pay_day,
                mode=target_mode, loan_type=f_type, target_payment=f_monthly_pay, target_date=f_target_date,
                admin_fee=f_fee, io_from=f_io_start if f_io_enable else None, io_to=f_io_end if f_io_enable else None
            )
            
            if df.empty: st.warning("Calc Error")
            else:
                last_row = df.iloc[-1]
                saved_payment_val = f_monthly_pay
                if target_mode == "date":
                    if f_type == "Serial":
                         months = len(df[df['Status'] == 'Payment'])
                         if months > 0: saved_payment_val = f_balance / months
                    else: saved_payment_val = df[df["Status"] == "Payment"]["Total Payment"].mean()

                st.session_state["last_loan_calc"] = {
                    "df": df,
                    "meta": {
                        "name": f_name, "balance": f_balance, "rate": f_rate, 
                        "mode": target_mode, "fee": f_fee, "type": f_type,
                        "day": f_pay_day, "from": f_pay_from, "start": f_start_date,
                        "t_date": f_target_date, "pay_in": float(saved_payment_val),
                        "io_en": f_io_enable, "io_s": f_io_start, "io_e": f_io_end
                    }
                }

        if "last_loan_calc" in st.session_state:
            res = st.session_state["last_loan_calc"]
            df = res["df"]
            meta = res["meta"]
            
            st.markdown("### 📊 Results")
            m1, m2, m3, m4 = st.columns(4)
            last_row = df.iloc[-1]
            total_interest = df["Interest"].sum()
            total_fees = df["Admin Fee"].sum()
            m1.metric("Payoff", last_row["Date"].strftime("%b %Y") if last_row['End Balance'] < 1 else "Never")
            m2.metric("Total Interest", f"{total_interest:,.0f} kr")
            m3.metric("Type", meta['type'])
            m4.metric("Total Cost", f"{(total_interest + total_fees + meta['balance']):,.0f} kr")

            tab_chart, tab_data, tab_save = st.tabs(["📈 Chart", "📋 Table", "💾 Save"])
            with tab_chart:
                fig = px.area(df, x="Date", y="End Balance", title="Projected Balance")
                st.plotly_chart(fig, use_container_width=True)
            with tab_data:
                # Updated to use width="stretch" to avoid deprecation warning
                st.dataframe(
                    df.style.format({c: "{:,.2f}" for c in ["Start Balance", "Interest", "Principal", "Total Payment", "End Balance"]}),
                    width="stretch"
                )
            with tab_save:
                if st.button("💾 Save to Database", key="btn_save_final"):
                    clean_record = _sanitize_record({
                        "name": meta['name'], "balance": meta['balance'], "interest_rate": meta['rate'],
                        "min_payment": meta['pay_in'], "admin_fee": meta['fee'], "payment_day": int(meta['day']),
                        "pay_from_account": meta['from'], "start_date": meta['start'],
                        "target_date": meta['t_date'] if meta['mode'] == 'date' else None,
                        "calculation_mode": meta['mode'], "loan_type": meta['type'],
                        "interest_only_from": meta['io_s'] if meta['io_en'] else None,
                        "interest_only_to": meta['io_e'] if meta['io_en'] else None,
                        "user_id": str(user_id)
                    })
                    add_record_db("loans", clean_record)
                    st.session_state["loan_data_version"] += 1 
                    st.success(f"Loan '{meta['name']}' saved!")
                    del st.session_state["last_loan_calc"]
                    st.rerun()