# components/budget.py
from __future__ import annotations
import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
from dateutil.relativedelta import relativedelta
import altair as alt

from core.db_operations import (
    load_data_db, 
    execute_query_db, 
    add_record_db,
    get_connection
)
from config.i18n import t
lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

# ============================================================
# 🛠️ DB MIGRATION
# ============================================================
def check_and_migrate_budget_schema():
    """Ensures the budget_rules table has the necessary columns."""
    try:
        df = load_data_db("budget_rules")
        if not df.empty and "transfer_to_account" not in df.columns:
            with get_connection() as conn:
                conn.execute("ALTER TABLE budget_rules ADD COLUMN transfer_to_account TEXT")
                conn.commit()
    except Exception:
        pass

# ============================================================
# 🧠 LOGIC: BUDGET ENGINE
# ============================================================
def get_active_budget_rules():
    df = load_data_db("budget_rules")
    if df.empty:
        return pd.DataFrame(columns=["id", "category", "amount", "frequency", "start_date", "is_active", "transfer_to_account"])
    
    if "transfer_to_account" not in df.columns:
        df["transfer_to_account"] = None
        
    return df

def calculate_monthly_budget_target(month_date: date, rules_df: pd.DataFrame) -> pd.DataFrame:
    if rules_df.empty:
        return pd.DataFrame(columns=["category", "Target", "transfer_to_account"])

    potential_targets = []
    
    for _, row in rules_df.iterrows():
        if not bool(row["is_active"]): 
            continue
            
        freq = row["frequency"]
        try:
            start_val = row["start_date"]
            start_dt = pd.to_datetime(start_val).date() if isinstance(start_val, str) else start_val.date()
        except: 
            continue

        amount = float(row["amount"])
        cat = row["category"]
        transfer_to = row.get("transfer_to_account")
        
        if month_date < start_dt.replace(day=1): 
            continue

        is_due = False
        diff_months = (month_date.year - start_dt.year) * 12 + (month_date.month - start_dt.month)
        
        if freq == "Monthly": is_due = True
        elif freq == "Quarterly": is_due = (diff_months % 3 == 0)
        elif freq == "Yearly": is_due = (diff_months % 12 == 0)
        elif freq == "Bi-Monthly": is_due = (diff_months % 2 == 0)
        elif freq == "Semi-Annually": is_due = (diff_months % 6 == 0)

        if is_due:
            potential_targets.append({
                "category": cat, 
                "Target": amount, 
                "start_date": start_dt,
                "transfer_to_account": transfer_to
            })
    
    if not potential_targets:
        return pd.DataFrame(columns=["category", "Target", "transfer_to_account"])
    
    df_hits = pd.DataFrame(potential_targets).sort_values(by="start_date", ascending=False)
    df_final = df_hits.drop_duplicates(subset="category", keep="first")
    
    return df_final

def get_budget_vs_actual(selected_month_iso: str):
    y, m = map(int, selected_month_iso.split("-"))
    month_date = date(y, m, 1)
    
    rules = get_active_budget_rules()
    df_targets = calculate_monthly_budget_target(month_date, rules)
    
    if not df_targets.empty:
        df_targets_sum = df_targets.groupby("category", as_index=False)["Target"].sum()
    else:
        df_targets_sum = pd.DataFrame(columns=["category", "Target"])

    df_tx = load_data_db("transactions")
    if not df_tx.empty:
        df_tx["date"] = pd.to_datetime(df_tx["date"], format='ISO8601', errors="coerce")
        
        exclude_cats = ["Transfer", "Opening Balance", "Unknown", "Balance Adjustment"]
        
        mask = (
            (df_tx["date"].dt.strftime("%Y-%m") == selected_month_iso) & 
            (df_tx["type"].isin(["Expense", "Income"])) &
            (~df_tx["category"].isin(exclude_cats))
        )
        actuals = df_tx[mask].groupby("category")["amount"].sum().reset_index()
        actuals.rename(columns={"amount": "Actual"}, inplace=True)
    else:
        actuals = pd.DataFrame(columns=["category", "Actual"])
        
        # Option 1: Explicitly set the option at the top of your file
    pd.set_option('future.no_silent_downcasting', True)
    df_merged = pd.merge(df_targets_sum, actuals, on="category", how="outer").fillna(0)

    # OR Option 2: Use infer_objects as recommended by the error
    # Replace the broken line 126 with this:
    df_merged = pd.merge(df_targets_sum, actuals, on="category", how="outer").fillna(0).infer_objects(copy=False)  
    if df_merged.empty:
        return pd.DataFrame(columns=["category", "SignedTarget", "SignedActual", "Diff", "Status"])

    cat_df = load_data_db("categories")
    cat_type_map = dict(zip(cat_df["name"], cat_df["type"])) if not cat_df.empty else {}

    def apply_signed_logic(row):
        c_type = cat_type_map.get(row["category"], "Expense")
        raw_target = row["Target"]
        raw_actual = row["Actual"]
        
        if c_type == "Income":
            return [raw_target, raw_actual]
        else:
            return [-abs(raw_target), -abs(raw_actual)]

    df_merged[["SignedTarget", "SignedActual"]] = df_merged.apply(apply_signed_logic, axis=1, result_type="expand")

    def get_status(row):
        t = row["SignedTarget"]
        a = row["SignedActual"]
        if t == 0 and a == 0: return "Unbudgeted"
        if a >= t: return "✅ Good"
        else: return "⚠️ Attention"

    df_merged["Diff"] = df_merged["SignedActual"] - df_merged["SignedTarget"]
    df_merged["Status"] = df_merged.apply(get_status, axis=1)
    
    return df_merged.sort_values(by="SignedTarget", ascending=False)

def _get_balance_at_date(account_name: str, target_date: date) -> float:
    """Calculates account balance including all transactions up to target_date."""
    df_tx = load_data_db("transactions")
    if df_tx.empty:
        return 0.0
    
    df_tx["date_dt"] = pd.to_datetime(df_tx["date"], format='ISO8601', errors="coerce").dt.date
    
    df_acc = df_tx[
        (df_tx["account"] == account_name) & 
        (df_tx["date_dt"] <= target_date)
    ].copy()
    
    if df_acc.empty:
        return 0.0
        
    def sign_amt(row):
        amt = float(row["amount"])
        t = str(row["type"]).strip().lower()
        if t in ["income", "opening balance", "deposit", "refund"]: return amt
        elif t in ["expense", "transfer", "withdrawal", "payment"]: return -abs(amt)
        return 0.0
        
    return df_acc.apply(sign_amt, axis=1).sum()

# ============================================================
# 🔮 SHARED INTELLIGENCE: NEW FORECAST ENGINE
# ============================================================
def get_projection_data(start_balance: float, months: int, selected_account_view: str, scenario_adjustments: list = None):
    rules = get_active_budget_rules()
    today = date.today().replace(day=1)
    
    cat_df = load_data_db("categories")
    cat_type_map = dict(zip(cat_df["name"], cat_df["type"])) if not cat_df.empty else {}
    
    adj_map = {}
    if scenario_adjustments:
        for item in scenario_adjustments:
            adj_map[item['category']] = item['adjustment']
    
    projection = []
    current_bal = start_balance
    
    for i in range(months):
        future_date = today + relativedelta(months=i)
        month_iso = future_date.strftime("%Y-%m")
        
        df_targets = calculate_monthly_budget_target(future_date, rules)
        monthly_net_change = 0.0
        
        if not df_targets.empty:
            for _, row in df_targets.iterrows():
                cat = row["category"]
                amt = row["Target"]
                
                if cat in adj_map:
                    amt += adj_map[cat]

                transfer_dest = row.get("transfer_to_account")
                c_type = cat_type_map.get(cat, "Expense")
                
                if cat in ["Opening Balance", "Unknown", "Balance Adjustment"]:
                    continue

                if transfer_dest and pd.notna(transfer_dest) and transfer_dest != "None":
                    if selected_account_view == transfer_dest:
                        monthly_net_change += amt
                    elif "Brukskonto" in selected_account_view or "Debit" in selected_account_view:
                         monthly_net_change -= amt
                else:
                    is_savings_view = "Saving" in selected_account_view
                    if not is_savings_view:
                        if c_type == "Income":
                            monthly_net_change += amt
                        else:
                            monthly_net_change -= amt
        
        if i > 0:
            current_bal += monthly_net_change
            
        projection.append({"Month": month_iso, "Predicted Balance": current_bal})
        
    return pd.DataFrame(projection)

# ============================================================
# 🖥️ RENDERERS
# ============================================================
def render_budget_planner():
    st.markdown("#### 🛠️ Budget Planner")
    st.caption("Set 'Transfer To' for savings rules to see them grow in the forecast.")
    check_and_migrate_budget_schema()
    
    if "budget_rules_df" not in st.session_state:
        df = get_active_budget_rules()
        if "start_date" in df.columns:
            df["start_date"] = pd.to_datetime(df["start_date"])
        if "is_active" in df.columns:
            df["is_active"] = df["is_active"].astype(bool)
        st.session_state["budget_rules_df"] = df

    cat_options = load_data_db("categories")["name"].tolist()
    acc_options = ["None"] + load_data_db("accounts")["name"].tolist()

    edited_rules = st.data_editor(
        st.session_state["budget_rules_df"], 
        num_rows="dynamic",
        column_config={
            "category": st.column_config.SelectboxColumn("Category", options=cat_options, required=True),
            "amount": st.column_config.NumberColumn("Amount", min_value=0, format="%d"),
            "frequency": st.column_config.SelectboxColumn("Frequency", options=["Monthly", "Quarterly", "Yearly"], required=True),
            "start_date": st.column_config.DateColumn("Start Date"),
            "transfer_to_account": st.column_config.SelectboxColumn("Transfer To", options=acc_options),
            "is_active": st.column_config.CheckboxColumn("Active"),
        },
        use_container_width=True,
        hide_index=True,
        key="budget_rules_editor"
    )
    
    if st.button("💾 Save Budget Rules", type="primary"):
        save_df = edited_rules.copy()
        save_df["start_date"] = save_df["start_date"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None)
        save_df["transfer_to_account"] = save_df["transfer_to_account"].replace("None", None)
        
        execute_query_db("DELETE FROM budget_rules") 
        with get_connection() as conn:
            save_df.to_sql("budget_rules", conn, if_exists="append", index=False)
        st.success("Updated!")
        del st.session_state["budget_rules_df"]
        st.rerun()

def render_month_view():
    c1, c2 = st.columns([1, 3])
    with c1:
        today = date.today()
        date_range = [today + relativedelta(months=i) for i in range(-12, 13)]
        options = [d.strftime("%Y-%m") for d in date_range]
        current_iso = today.strftime("%Y-%m")
        try:
            default_ix = options.index(current_iso)
        except ValueError:
            default_ix = 0
        selected_month = st.selectbox("Select Period", options, index=default_ix)

    df_view = get_budget_vs_actual(selected_month)
    if df_view.empty:
        st.info("No budget data.")
        return

    net_budget = df_view["SignedTarget"].sum()
    net_actual = df_view["SignedActual"].sum()
    surplus_deficit = df_view["Diff"].sum()
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Net Budget", f"{net_budget:,.0f} kr")
    k2.metric("Net Actual", f"{net_actual:,.0f} kr", delta=f"{surplus_deficit:,.0f} diff")
    k3.metric("Surplus / Deficit", f"{surplus_deficit:,.0f} kr")
    
    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "SignedTarget": st.column_config.NumberColumn("Target", format="%d kr"),
            "SignedActual": st.column_config.NumberColumn("Actual", format="%d kr"),
            "Diff": st.column_config.NumberColumn("Diff", format="%d kr"),
        },
        column_order=["category", "SignedTarget", "SignedActual", "Diff", "Status"]
    )

def render_forecast():
    st.markdown("#### 🔮 12-Month Liquidity Forecast")
    
    acc_df = load_data_db("accounts")
    if acc_df.empty: 
        return
    
    acc_names = acc_df["name"].tolist()
    default_idx = acc_names.index("Brukskonto") if "Brukskonto" in acc_names else 0
    selected_acc = st.selectbox("Forecast for:", options=acc_names, index=default_idx)
    
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_of_current_month = date(today.year, today.month, last_day)
    current_balance = _get_balance_at_date(selected_acc, end_of_current_month)
    
    st.caption(f"Starting Balance (End of {end_of_current_month.strftime('%B')}): **{current_balance:,.0f} kr**")
    
    df_base = get_projection_data(current_balance, 12, selected_acc)
    df_base["Scenario"] = "Current Plan"

    ai_scenarios = st.session_state.get("ai_scenarios", [])
    if ai_scenarios:
        df_ai = get_projection_data(current_balance, 12, selected_acc, scenario_adjustments=ai_scenarios)
        df_ai["Scenario"] = "AI Scenario"
        plot_df = pd.concat([df_base, df_ai])
        
        # We create the text string first to avoid backslashes inside the f-string
        adjustment_text = ", ".join([f"{d.get('category')}: {d.get('adjustment')} kr" for d in ai_scenarios])
        st.info(f"💡 Simulating AI adjustments: {adjustment_text}")
    else:
        plot_df = df_base
    
    chart = alt.Chart(plot_df).mark_line(point=True, strokeWidth=3).encode(
        x=alt.X('Month', axis=alt.Axis(labelAngle=-45)),
        y=alt.Y('Predicted Balance', title='Est. Balance (kr)', scale=alt.Scale(zero=False)),
        color=alt.Color('Scenario', scale=alt.Scale(domain=['Current Plan', 'AI Scenario'], range=['#1f77b4', '#ff7f0e'])),
        tooltip=['Month', 'Predicted Balance', 'Scenario']
    ).properties(height=350)
    
    zero_rule = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='red', strokeDash=[5,5]).encode(y='y')
    st.altair_chart(chart + zero_rule, use_container_width=True)
    
    if ai_scenarios:
        if st.button("Reset AI Scenario"):
            st.session_state["ai_scenarios"] = []
            st.rerun()

def render_budget():
    check_and_migrate_budget_schema()
    st.markdown("### 📊 Budget & Financial Planning")
    tabs = st.tabs(["📉 Month View", "🛠️ Budget Planner", "🔮 Forecast"])
    with tabs[0]: render_month_view()
    with tabs[1]: render_budget_planner()
    with tabs[2]: render_forecast()