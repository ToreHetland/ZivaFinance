# components/overview.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import calendar
import os
from datetime import datetime, date, timedelta
from core.db_operations import load_data_db

# Logic imports from our Budget Engine
from components.budget import get_projection_data, get_budget_vs_actual, _get_balance_at_date
from config.config import format_currency, get_setting
from core.language_manager import t, get_time_greeting_key
from config.i18n import t

lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

# ============================================================
# 🎨 PREMIUM UI & ICON HELPERS
# ============================================================

def get_category_icon_path(category_name: str) -> str | None:
    """
    Checks for an AI-generated Nano Banana icon in local storage.
    FIXES: NameError in render_overview
    """
    safe_name = str(category_name).replace(" ", "_").lower()
    path = f"assets/icons/categories/{safe_name}.png"
    if os.path.exists(path):
        return path
    return None

def _kpi_card_html(label, value, delta=None, color="#333"):
    """
    Premium Glassmorphism Card with Backdrop Blur and Subdued Borders.
    """
    if delta and delta != "0.0%":
        d_color = "#10B981" if "+" in str(delta) or str(delta).startswith("0") else "#EF4444"
        if "Expense" in label:
             d_color = "#EF4444" if "+" in str(delta) else "#10B981"
        delta_html = f"<div style='color: {d_color}; font-size: 0.8rem; font-weight: 700; margin-top: 4px;'>{delta} vs last month</div>"
    else:
        delta_html = "<div style='height: 20px;'></div>"

    return f"""
    <div class="ziva-card" style='padding: 20px; display: flex; flex-direction: column; justify-content: space-between; height: 150px; border-left: 4px solid {color};'>
        <div style='color: #64748b; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;'>{label}</div>
        <div>
            <div style='color: {color}; font-size: 1.8rem; font-weight: 800; line-height: 1.1;'>{value}</div>
            {delta_html}
        </div>
    </div>
    """

# ============================================================
# 🧠 DATA PROCESSING
# ============================================================
def _get_financial_snapshot():
    """Calculates Net Worth, Flow, Trends, and integrates Budget/Forecast logic."""
    acc_df = load_data_db("accounts")
    net_worth = cash_assets = credit_debt = 0.0
    
    if not acc_df.empty:
        acc_df["balance"] = pd.to_numeric(acc_df["balance"], errors="coerce").fillna(0.0)
        net_worth = acc_df["balance"].sum()
        if "account_type" in acc_df.columns:
            cash_assets = acc_df[~acc_df["account_type"].isin(["Credit Card", "Loan"])]["balance"].sum()
            credit_debt = acc_df[acc_df["account_type"].isin(["Credit Card", "Loan"])]["balance"].sum()

    tx_df = load_data_db("transactions")
    income_mo = expense_mo = savings_rate = savings_delta = savings_amount = 0.0
    recent_tx = pd.DataFrame()
    trend_data = pd.DataFrame() 

    if not tx_df.empty:
        tx_df["date"] = pd.to_datetime(tx_df["date"], errors="coerce")
        tx_df["amount"] = pd.to_numeric(tx_df["amount"], errors="coerce").fillna(0.0)
        
        today = datetime.today()
        curr_month_str = today.strftime("%Y-%m")
        prev_month_str = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        tx_df["period"] = tx_df["date"].dt.to_period("M").astype(str)
        
        salary_accounts = ["Brukskonto", "Salary", "Lønnskonto"]
        income_mo = tx_df[(tx_df["period"] == curr_month_str) & (tx_df["type"] == "Income") & (tx_df["account"].isin(salary_accounts))]["amount"].sum()

        exclude = ["Transfer", "Overføring", "Adjustment", "Balansejustering"]
        expense_mo = tx_df[(tx_df["period"] == curr_month_str) & (tx_df["type"] == "Expense") & (~tx_df["category"].isin(exclude))]["amount"].sum()
        
        savings_amount = income_mo - expense_mo
        if income_mo > 0:
            savings_rate = (savings_amount / income_mo) * 100
            
        prev_income = tx_df[(tx_df["period"] == prev_month_str) & (tx_df["type"] == "Income") & (tx_df["account"].isin(salary_accounts))]["amount"].sum()
        prev_expense = tx_df[(tx_df["period"] == prev_month_str) & (tx_df["type"] == "Expense") & (~tx_df["category"].isin(exclude))]["amount"].sum()
        prev_savings_rate = ((prev_income - prev_expense) / prev_income * 100) if prev_income > 0 else 0
        savings_delta = savings_rate - prev_savings_rate

        recent_tx = tx_df.sort_values("date", ascending=False).head(6)

    curr_iso = datetime.now().strftime("%Y-%m")
    budget_view = get_budget_vs_actual(curr_iso)
    total_target = abs(budget_view[budget_view["SignedTarget"] < 0]["SignedTarget"].sum())
    total_actual = abs(budget_view[budget_view["SignedActual"] < 0]["SignedActual"].sum())
    budget_usage = min(total_actual / total_target, 1.2) if total_target > 0 else 0.0

    main_acc = "Brukskonto"
    last_day = calendar.monthrange(date.today().year, date.today().month)[1]
    curr_bal = _get_balance_at_date(main_acc, date.today().replace(day=last_day))
    forecast_df = get_projection_data(curr_bal, 6, main_acc)

    return {
        "net_worth": net_worth, "cash_assets": cash_assets, "credit_debt": credit_debt,
        "income_mo": income_mo, "expense_mo": expense_mo, "savings_rate": savings_rate,
        "savings_amount": savings_amount, "savings_delta": savings_delta,
        "recent_tx": recent_tx, "budget_usage": budget_usage, 
        "remaining_budget": max(total_target - total_actual, 0),
        "forecast_df": forecast_df
    }

# ============================================================
# 🚀 MAIN RENDERER
# ============================================================

def render_overview():
    data = _get_financial_snapshot()
    persona = get_setting("ai_persona", "Professional Analyst")
    current_user = st.session_state.get("username", "User")
    greeting_base = t(get_time_greeting_key())
    
    # --- HEADER ---
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"## {greeting_base}, {current_user}!")
        st.caption(f"Strategy view for **{datetime.now().strftime('%B %Y')}**")
    with c2:
        insight = "Everything looks stable."
        if data["budget_usage"] > 1.0: 
            insight = "⚠️ Budget exceeded! We should adjust the planner for next month."
        elif data["savings_rate"] > 25: 
            insight = f"🚀 Exceptional! Your {data['savings_rate']:.1f}% savings rate is accelerating your goals."
        
        st.markdown(f"""
            <div class="ziva-card" style="padding: 15px; border-left: 5px solid #3b82f6; background: rgba(59, 130, 246, 0.1);">
                <strong style="color: #1e40af;">🤖 {persona} Insight:</strong><br>
                <span style="font-size: 0.9rem; color: #1e3a8a;">{insight}</span>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 1. KPI CARDS (GLASS) ---
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(_kpi_card_html("Net Worth", f"{data['net_worth']:,.0f} kr", color="#3b82f6"), unsafe_allow_html=True)
    k2.markdown(_kpi_card_html("Monthly Income", f"{data['income_mo']:,.0f} kr", color="#10B981"), unsafe_allow_html=True)
    k3.markdown(_kpi_card_html("Monthly Expenses", f"{data['expense_mo']:,.0f} kr", color="#f43f5e"), unsafe_allow_html=True)
    
    savings_display = f"{data['savings_rate']:.1f}%"
    savings_subtext = f"({data['savings_amount']:,.0f} kr)"
    k4.markdown(_kpi_card_html(
        "Savings Rate", 
        f"{savings_display} <br><span style='font-size: 0.85rem; color: #64748b;'>{savings_subtext}</span>", 
        delta=f"{data['savings_delta']:+.1f}%",
        color="#8b5cf6"
    ), unsafe_allow_html=True)

    st.markdown("---")

    # --- 2. MAIN DASHBOARD GRID ---
    left_col, right_col = st.columns([2, 1], gap="large")

    with left_col:
        st.markdown("#### 🌊 6-Month Liquidity Forecast")
        if not data["forecast_df"].empty:
            f_chart = data["forecast_df"]
            fig = go.Figure()
            # Gradient Fill Area
            fig.add_trace(go.Scatter(
                x=f_chart['Month'], y=f_chart['Predicted Balance'],
                mode='lines+markers', name='Projected',
                line=dict(color='#3b82f6', width=4),
                fill='tozeroy', fillcolor='rgba(59, 130, 246, 0.1)'
            ))
            fig.update_layout(
                hovermode="x unified", height=320, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.1)')
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Cash vs Debt Map
        st.markdown("<br>", unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"""
                <div class="ziva-card" style="text-align:center; padding: 15px;">
                    <small style="color:#64748b">CASH ASSETS</small><br>
                    <span style="font-size: 1.2rem; font-weight:800; color:#10b981;">{data['cash_assets']:,.0f} kr</span>
                </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
                <div class="ziva-card" style="text-align:center; padding: 15px;">
                    <small style="color:#64748b">TOTAL DEBT</small><br>
                    <span style="font-size: 1.2rem; font-weight:800; color:#ef4444;">{data['credit_debt']:,.0f} kr</span>
                </div>
            """, unsafe_allow_html=True)

    with right_col:
        st.markdown("#### 🎯 Budget Health")
        usage = data["budget_usage"]
        bar_color = "#f43f5e" if usage > 1.0 else "#3b82f6"
        st.progress(min(usage, 1.0), text=f"{usage*100:.0f}% used")
        
        if data["remaining_budget"] > 0:
            st.success(f"**{data['remaining_budget']:,.0f} kr** left to spend.")
        else:
            st.error("Budget limits exceeded.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 🕒 Recent Insights")
        if not data["recent_tx"].empty:
            for _, row in data["recent_tx"].iterrows():
                is_inc = row['type'] == 'Income'
                color = "#10B981" if is_inc else "#1e293b"
                
                # Fetch icon path
                icon_path = get_category_icon_path(row['category'])
                
                st.markdown(f"""
                    <div style='display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(200,200,200,0.1);'>
                        <div style="margin-right: 12px; font-size: 1.2rem;">
                            {'🖼️' if icon_path else '📁'}
                        </div>
                        <div style="flex-grow: 1;">
                            <div style='font-weight: 700; font-size: 0.85rem; color: #334155;'>{row['payee']}</div>
                            <div style='font-size: 0.7rem; color: #94a3b8;'>{row['category']} • {row['date'].strftime('%d %b')}</div>
                        </div>
                        <div style='font-weight: 800; color: {color}; font-size: 0.9rem;'>
                            {'+' if is_inc else ''}{row['amount']:,.0f}
                        </div>
                    </div>
                """, unsafe_allow_html=True)