from __future__ import annotations

from datetime import date
from typing import Dict, Optional
import json
import os
import re

import pandas as pd
import streamlit as st

from core.db_operations import load_data_db
from config.config import format_currency, get_setting
from config.i18n import t

# ============================================================
# AI SERVICE (optional — don’t crash if missing)
# ============================================================
try:
    from services.ai_services import generate_advice  # type: ignore
except Exception:
    generate_advice = None


# ============================================================
# 🎨 BRANDED STRATEGIC UI
# ============================================================
def _apply_sexy_styles():
    st.markdown(f"""
    <style>
    .persona-container {{
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 15px; 
        padding: 10px 15px;
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }}
    .strategy-card {{
        background: white;
        padding: 8px 10px; 
        border-radius: 8px;
        border-bottom: 3px solid #3b82f6;
        box-shadow: 0 1px 3px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }}
    .strategy-card h3 {{
        margin: 0 !important;
        padding: 0 !important;
        font-size: 1.1rem !important; 
        font-weight: 700 !important;
    }}
    .strategy-card small {{
        font-size: 0.7rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        line-height: 1;
    }}
    div[data-testid="stChatMessage"] {{
        padding-top: 0.3rem !important;
        padding-bottom: 0.3rem !important;
        margin-top: -10px !important; 
        margin-bottom: 0px !important;
    }}
    .stChatInputContainer textarea {{
        font-size: 14px;
        min-height: 42px !important; 
    }}
    div.stButton > button {{
        padding-top: 0.1rem;
        padding-bottom: 0.1rem;
        min-height: 0px;
        height: auto;
        font-size: 13px;
    }}
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# 🧠 STRATEGIC CONTEXT BUILDER (MULTI-USER AWARE)
# ============================================================
def _build_strategic_context() -> Dict:
    uid = st.session_state.get("username") or "default"

    
    # Isolation: Only load data for the active user
    tx = load_data_db("transactions", user_id=uid)
    accounts = load_data_db("accounts", user_id=uid)
    loans = load_data_db("loans", user_id=uid)
    
    context = {
        "net_worth": float(accounts["balance"].sum()) if not accounts.empty else 0.0,
        "existing_loans": loans[["name", "balance"]].to_dict('records') if not loans.empty else [],
        "monthly": {"income": 0.0, "expenses": 0.0, "disposable": 0.0},
        "categories": {}
    }

    if not tx.empty:
        tx["date"] = pd.to_datetime(tx["date"], errors="coerce")
        exclude = ["Transfer", "Overføring", "Overforing", "Adjustment", "Balansejustering", "Balance Adjustment"]
        clean_tx = tx[~tx["type"].isin(exclude) & ~tx["category"].isin(exclude)]
        
        m_tx = clean_tx[clean_tx["date"].dt.to_period("M") == pd.Timestamp.today().to_period("M")]
        inc = m_tx[m_tx["type"] == "Income"]["amount"].sum()
        exp = m_tx[m_tx["type"] == "Expense"]["amount"].sum()
        
        context["monthly"] = {"income": float(inc), "expenses": float(exp), "disposable": float(inc - exp)}
        context["categories"] = m_tx[m_tx["type"] == "Expense"].groupby("category")["amount"].sum().to_dict()

    return context

# ============================================================
# 💬 RENDERER
# ============================================================
def render_ai_advisor():
    _apply_sexy_styles()
    uid = st.session_state.get("username") or "default"

    
    # 1. HEADER & LOGO
    persona = get_setting("ai_persona", "Professional Analyst")
    icon_path = os.path.join("assets", "icons", "ziva_icon.png")

    c_logo, c_header = st.columns([0.5, 4.5]) 
    with c_logo:
        if os.path.exists(icon_path):
            st.image(icon_path, width=65)
        else:
            st.markdown("<h1>🧠</h1>", unsafe_allow_html=True)
            
    with c_header:
        st.markdown(f"""
            <div class="persona-container">
                <div>
                    <div style="color: #64748b; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px;">Strategic Advisor</div>
                    <div style="color: #1e40af; font-size: 20px; font-weight: 700;">{persona}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # 2. PERFORMANCE RIBBON
    ctx = _build_strategic_context()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""<div class="strategy-card"><small>Total Liquidity</small><br><h3>{format_currency(ctx['net_worth'])}</h3></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="strategy-card"><small>Monthly Surplus</small><br><h3>{format_currency(ctx['monthly'].get('disposable', 0))}</h3></div>""", unsafe_allow_html=True)
    with col3:
        inc_val = ctx['monthly'].get('income', 0)
        savings_rate = (ctx['monthly']['disposable'] / inc_val * 100) if inc_val > 0 else 0
        st.markdown(f"""<div class="strategy-card"><small>Savings Rate</small><br><h3>{savings_rate:.1f}%</h3></div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    # 3. GOAL PLANNER
    with st.expander("🎯 Plan a New Strategic Goal", expanded=False):
        st.caption("Define a target and let AI map the financial path.")
        g1, g2, g3 = st.columns([3, 2, 1])
        with g1:
            goal_desc = st.text_input("Goal Name", placeholder="e.g., Car, House...", key="goal_desc_input", label_visibility="collapsed")
        with g2:
            goal_val = st.number_input("Budget", min_value=0, step=1000, key="goal_val_input", label_visibility="collapsed")
        with g3:
            plan_it = st.button("🚀", use_container_width=True, help="Plan Goal")

    # 4. CHAT HISTORY
    if "ai_chat_history" not in st.session_state:
        st.session_state["ai_chat_history"] = []
    
    chat_box = st.container(height=400)
    
    # 5. STRATEGIC TOOLS
    triggered_prompt = None
    st.caption("Strategic Intelligence Tools") 
    
    t1, t2, t3 = st.columns(3)
    with t1:
        if st.button("📊 Spending Insights", use_container_width=True, key="btn_spending_insights"): 
            triggered_prompt = "Analyze my spending patterns for this month."
    with t2:
        if st.button("📈 Savings Audit", use_container_width=True, key="btn_savings_audit"): 
            triggered_prompt = "Conduct a full savings audit."
    with t3:
        if st.button("🧹 Reset Chat", use_container_width=True, key="btn_reset_chat"): 
            st.session_state["ai_chat_history"] = []
            st.session_state["ai_scenarios"] = []
            st.rerun()

    user_input = st.chat_input("Ask your personal AI advisor...")
    final_query = None

    if plan_it and goal_desc:
        final_query = f"I want to plan for: {goal_desc}. Budget is {goal_val if goal_val > 0 else 'to be proposed'}."
    elif triggered_prompt:
        final_query = triggered_prompt
    elif user_input:
        final_query = user_input

# 6. AI EXECUTION ENGINE
    if final_query:
        st.session_state["ai_chat_history"].append({"role": "user", "content": final_query})
        
        current_date_ref = date.today().strftime("%Y-%m")
        
        # We define the JSON example as a standard string (no f-prefix)
        json_example = '{ "scenarios": [{ "month": "' + current_date_ref + '", "amount": -1000, "label": "Goal Name" }] }'
        
        # REMOVED the 'f' from the start of the prompt to stop SyntaxErrors
        sys_prompt = """
        PERSONALITY: {persona}.
        CONTEXT: Liquidity: {net_worth} NOK, Surplus: {surplus} NOK, Debt: {debt}.
        
        INSTRUCTIONS:
        1. All financial scenarios must start from {date_ref}.
        2. Propose a path: Savings vs Loan based on liquidity.
        3. Analyze spending patterns: {cats}.
        4. Provide 3 tiers of savings (Low, Medium, High effort).
        
        JSON RULE: Append a JSON scenario block for any goal exactly in this format:
        ```json 
        {json_ex}
        ```
        """.format(
            persona=persona,
            net_worth=ctx['net_worth'],
            surplus=ctx['monthly'].get('disposable', 0),
            debt=ctx['existing_loans'],
            date_ref=current_date_ref,
            cats=ctx.get('categories'),
            json_ex=json_example
        )
        
        with st.spinner("Analyzing strategy..."):
            if generate_advice:
                user_tx = load_data_db("transactions", user_id=uid)
                # Note: sys_prompt is now a clean string
                response, err, _ = generate_advice(user_tx, lang="en", question=sys_prompt + f"\nUser: {final_query}")
                
                if not err:
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                    if json_match:
                        try:
                            st.session_state["ai_scenarios"] = json.loads(json_match.group(1)).get("scenarios", [])
                            response = re.sub(r'```json.*?```', '\n\n✅ *Strategy integrated into Forecast.*', response, flags=re.DOTALL)
                        except: pass
                    
                    st.session_state["ai_chat_history"].append({"role": "assistant", "content": response})
                else:
                    st.error(f"Error: {response}")
            else:
                st.error("AI Service not initialized.")
        st.rerun()

    with chat_box:
        for msg in st.session_state["ai_chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])