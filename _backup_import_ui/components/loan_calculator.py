# components/loan_calculator.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from core.db_operations import add_record_db, load_data_db, execute_query_db
from config.i18n import t

lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

# ============================================================
# 🧮 LOGIC
# ============================================================
def _calculate_loan(principal, rate, years):
    r = (rate / 100.0) / 12.0
    n = int(years * 12)
    
    if n <= 0: return 0, 0, 0
    if r == 0:
        monthly = principal / n
    else:
        monthly = principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        
    total_payment = monthly * n
    total_interest = total_payment - principal
    return monthly, total_interest, total_payment

def _generate_schedule(principal, rate, years, monthly):
    r = (rate / 100.0) / 12.0
    n = int(years * 12)
    balance = principal
    data = []
    
    for i in range(1, n + 1):
        interest = balance * r
        # Handle last payment
        if i == n: 
            principal_pay = balance
            payment = balance + interest
        else:
            principal_pay = monthly - interest
            payment = monthly
            
        balance -= principal_pay
        data.append({
            "Month": i,
            "Balance": max(0, balance),
            "Interest": interest,
            "Principal": principal_pay
        })
    return pd.DataFrame(data)

# ============================================================
# 🎨 RENDERER
# ============================================================
def render_loan_calculator():
    st.header("🏦 Loan Planner")
    st.caption("Simulate loans and visualize your payoff schedule.")

    # --- 1. INPUTS (Top Bar) ---
    with st.container():
        c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1, 1, 1.5])
        with c1: name = st.text_input("Loan Name", value="Car Loan")
        with c2: amount = st.number_input("Amount", value=25000.0, step=1000.0, format="%.2f")
        with c3: rate = st.number_input("Rate (%)", value=5.5, step=0.1)
        with c4: years = st.number_input("Years", value=5, min_value=1)
        with c5: 
            st.write("") # Spacer
            st.write("") 
            calc_btn = st.button("🚀 Calculate", type="primary", use_container_width=True)

    st.markdown("---")

    # --- 2. RESULTS DASHBOARD ---
    if calc_btn or "loan_res" in st.session_state:
        # Persist inputs loosely
        monthly, tot_int, tot_pay = _calculate_loan(amount, rate, years)
        st.session_state["loan_res"] = True
        
        # KEY METRICS
        m1, m2, m3 = st.columns(3)
        with m1: 
            st.metric("Monthly Payment", f"{monthly:,.2f}")
        with m2: 
            st.metric("Total Interest", f"{tot_int:,.2f}", delta=f"{(tot_int/amount)*100:.1f}% cost", delta_color="inverse")
        with m3: 
            st.metric("Total Cost", f"{tot_pay:,.2f}")

        # CHARTS
        schedule_df = _generate_schedule(amount, rate, years, monthly)
        
        tab1, tab2 = st.tabs(["📊 Visuals", "📋 Schedule"])
        
        with tab1:
            col_chart1, col_chart2 = st.columns([1, 2])
            
            with col_chart1:
                # Donut Chart: Principal vs Interest
                fig_pie = go.Figure(data=[go.Pie(
                    labels=['Principal', 'Interest'], 
                    values=[amount, tot_int], 
                    hole=.6,
                    marker_colors=['#3B82F6', '#EF4444'] # Blue, Red
                )])
                fig_pie.update_layout(showlegend=False, margin=dict(t=30, b=0, l=0, r=0), height=250, title="Cost Breakdown")
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with col_chart2:
                # Area Chart: Balance Over Time
                fig_area = px.area(
                    schedule_df, x="Month", y="Balance", 
                    title="Payoff Trajectory",
                    color_discrete_sequence=['#10B981'] # Emerald
                )
                fig_area.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=250, xaxis_title="Months", yaxis_title="Remaining Debt")
                st.plotly_chart(fig_area, use_container_width=True)
        
        with tab2:
            st.dataframe(schedule_df, hide_index=True, use_container_width=True, height=300)

        # SAVE ACTION
        if st.button("💾 Save to History"):
            rec = {
                "loan_name": name, "principal": amount, "interest_rate": rate, 
                "loan_term_years": years, "monthly_payment": monthly
            }
            add_record_db("loans", rec)
            st.success("Saved!")

    # --- 3. SAVED LOANS ---
    st.markdown("### Saved Loans")
    history = load_data_db("loans")
    if not history.empty:
        for i, row in history.iterrows():
            with st.expander(f"{row.get('loan_name', 'Loan')} — {float(row.get('monthly_payment',0)):,.2f} / mo"):
                st.write(f"Amount: {float(row.get('principal',0)):,.2f} @ {float(row.get('interest_rate',0))}% for {row.get('loan_term_years')} years")
                if st.button("Delete", key=f"del_loan_{i}"):
                    execute_query_db(f"DELETE FROM loans WHERE id={row['id']}")
                    st.rerun()