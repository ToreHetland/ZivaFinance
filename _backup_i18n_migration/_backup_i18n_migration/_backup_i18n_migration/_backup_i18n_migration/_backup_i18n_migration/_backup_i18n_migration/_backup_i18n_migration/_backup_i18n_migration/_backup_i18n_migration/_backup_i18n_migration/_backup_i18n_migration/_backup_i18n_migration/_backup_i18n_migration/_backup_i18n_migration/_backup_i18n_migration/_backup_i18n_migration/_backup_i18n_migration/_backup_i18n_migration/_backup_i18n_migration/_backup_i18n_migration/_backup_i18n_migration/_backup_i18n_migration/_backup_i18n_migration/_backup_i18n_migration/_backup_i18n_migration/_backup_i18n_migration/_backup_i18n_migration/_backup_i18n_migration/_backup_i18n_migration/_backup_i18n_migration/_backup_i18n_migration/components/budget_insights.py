# components/budget_insights.py
"""
AI-powered Budget Insights
--------------------------
Analyzes current budgets vs actuals and asks Gemini / OpenAI
for natural-language insight summaries and suggestions.
"""

import streamlit as st
import pandas as pd
from datetime import date
from core.db_operations import load_data_db
from config.config import format_currency
from services.ai_services import get_ai_chat_response  # your existing AI wrapper
from config.i18n import t

# ============================================================
# Entry point
# ============================================================

def render_budget_insights():
    st.header("🤖 Budget Insights")

    # ---- Load data
    tx = load_data_db("transactions")
    budgets = load_data_db("budgets")
    cats = load_data_db("categories")

    if tx.empty or budgets.empty:
        st.info("Add transactions and budgets to generate insights.")
        return

    # ---- Month selector
    tx["date"] = pd.to_datetime(tx["date"], errors="coerce")
    tx["month"] = tx["date"].dt.to_period("M").astype(str)
    months = sorted(tx["month"].unique().tolist(), reverse=True)
    selected_month = st.selectbox("Select Month", months, index=0)

    # ---- Build summary table
    txm = tx[tx["month"] == selected_month]
    if txm.empty:
        st.info("No transactions for this month.")
        return

    income = txm.loc[txm["type"] == "Income", "amount"].sum()
    expense = txm.loc[txm["type"] == "Expense", "amount"].sum()
    net = income - expense

    st.markdown(
        f"""
    ### 📅 {selected_month}
    | Metric | Amount |
    |---------|--------:|
    | **Income** | {format_currency(income)} |
    | **Expenses** | {format_currency(expense)} |
    | **Net Balance** | {format_currency(net)} |
    """,
        unsafe_allow_html=True,
    )

    # ---- Category performance vs budget
    budgets["month"] = budgets["month"].astype(str).str[:7]
    bm = budgets[budgets["month"] == selected_month]
    bm = bm[bm["period"] == "Monthly"]

    actuals = (
        txm.groupby(["type", "category"])["amount"].sum().reset_index()
        if not txm.empty
        else pd.DataFrame(columns=["type", "category", "amount"])
    )

    merged = bm.merge(
        actuals,
        left_on=["budget_type", "category"],
        right_on=["type", "category"],
        how="left",
    ).fillna({"amount": 0.0})

    merged["diff"] = merged["amount"] - merged["budget_amount"]
    merged["pct"] = (
        (merged["amount"] / merged["budget_amount"] * 100).round(1).replace([pd.NA, pd.NaT], 0)
    )

    st.subheader("📊 Category Performance")
    st.dataframe(
        merged[["budget_type", "category", "budget_amount", "amount", "diff", "pct"]].rename(
            columns={
                "budget_type": "Type",
                "category": "Category",
                "budget_amount": "Budget",
                "amount": "Actual",
                "diff": "Δ",
                "pct": "% Used",
            }
        ),
        hide_index=True,
    )

    st.markdown("---")
    st.subheader("💬 AI Analysis")

    # ---- Prompt engineering
    sample_rows = merged.sort_values("budget_type").head(25)
    txt_summary = sample_rows.to_string(index=False)

    prompt = f"""
    You are a personal finance assistant.
    Analyze the following monthly data and give a concise, actionable insight summary.
    Highlight overspending categories, under-utilized budgets, and overall financial health.
    Provide bullet-point recommendations.

    Month: {selected_month}
    Total Income: {format_currency(income)}
    Total Expense: {format_currency(expense)}
    Net: {format_currency(net)}

    Category details:
    {txt_summary}
    """

    if st.button("🧠 Generate AI Insights"):
        with st.spinner("Thinking..."):
            try:
                ai_text = get_ai_chat_response(prompt)
                st.success("✅ Insights generated")
                st.markdown(ai_text)
            except Exception as e:
                st.error(f"Failed to get AI response: {e}")

    st.caption("Powered by Gemini / OpenAI via your `ai_services.py` connector.")
