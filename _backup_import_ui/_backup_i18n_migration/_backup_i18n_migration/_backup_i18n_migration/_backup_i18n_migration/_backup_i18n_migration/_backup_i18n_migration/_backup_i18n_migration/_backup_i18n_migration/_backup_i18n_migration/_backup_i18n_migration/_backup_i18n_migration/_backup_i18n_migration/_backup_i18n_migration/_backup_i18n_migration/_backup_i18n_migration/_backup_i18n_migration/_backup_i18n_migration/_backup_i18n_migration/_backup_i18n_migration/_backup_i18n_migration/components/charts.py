# components/charts.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

from config.i18n import t
from config.config import format_currency, get_setting
from core.db_operations import load_data_db
from config.i18n import t
lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

# ============================================================
# 🎨 THEME-AWARE PALETTE
# ============================================================

def get_theme_palette():
    theme = get_setting("theme", "Light").lower()
    if "dark" in theme or "midnight" in theme or "retro" in theme:
        return {
            "bg": "#0B1220", "paper": "#111A2E", "text": "#E8EEF9", "grid": "#1F2937",
            "income": "#10B981", "expense": "#EF4444", "blue": "#3B82F6",
            "accent": "#8B5CF6", "categorical": px.colors.qualitative.Pastel
        }
    else:
        return {
            "bg": "#F8FAFC", "paper": "#FFFFFF", "text": "#0F172A", "grid": "#E2E8F0",
            "income": "#059669", "expense": "#DC2626", "blue": "#2563EB",
            "accent": "#7C3AED", "categorical": px.colors.qualitative.Vivid
        }

# ============================================================
# 🧠 DATA PREPARATION
# ============================================================

def _prepare_transactions_analytics(exclude_categories=None):
    df = load_data_db("transactions")
    if df.empty: return df
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["amount"] = pd.to_numeric(df.get("amount", 0), errors="coerce").fillna(0.0)
    df["type"] = df["type"].astype(str).str.strip().str.title()
    
    # Filter Balance Adjustments & Transfers
    exclude_list = ["Transfer", "Overføring", "Overforing", "Adjustment", "Balansejustering", "Balance Adjustment"]
    pattern = "overføring|transfer|adjustment|balansejustering"
    
    mask_exclude = (
        df["type"].isin(exclude_list) | 
        df["category"].isin(exclude_list) |
        df["payee"].astype(str).str.lower().str.contains(pattern, na=False) |
        df["description"].astype(str).str.lower().str.contains(pattern, na=False)
    )
    df = df[~mask_exclude]
    
    if exclude_categories:
        df = df[~df["category"].isin(exclude_categories)]
    
    df["category"] = df["category"].fillna("Uncategorized").replace("", "Uncategorized")
    df["payee"] = df["payee"].fillna("Unknown").replace("", "Unknown")
    return df

# ============================================================
# 📊 Main Analytics Dashboard
# ============================================================

def render_analytics_dashboard(prefix: str = "analytics"):
    p = get_theme_palette()
    st.header("🚀 Edge Financial Analytics")

    c1, c2, c3, c4 = st.columns([1, 1, 1.5, 1.5])
    with c1: start_date = st.date_input("From", value=datetime.today().replace(month=1, day=1))
    with c2: end_date = st.date_input("To", value=datetime.today())
    
    all_cats = sorted(load_data_db("categories")["name"].unique().tolist()) if not load_data_db("categories").empty else []
    with c3:
    # Get the saved defaults from settings
        saved_defaults = get_setting("analytics_excluded_categories", ["Transfer"])
        
        # Filter the defaults to only include categories that actually exist in all_cats
        valid_defaults = [cat for cat in saved_defaults if cat in all_cats]
        
        ignored_cats = st.multiselect(
            "Exclude Categories", 
            options=all_cats, 
            default=valid_defaults
        )
    df = _prepare_transactions_analytics(exclude_categories=ignored_cats)
    if df.empty:
        st.info("No data available.")
        return

    mask = (df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))
    filtered_df = df[mask].copy()
    
    with c4:
        accs = ["All Accounts"] + sorted(filtered_df["account"].unique().tolist())
        acc_filter = st.multiselect("Accounts", accs, default=["All Accounts"])
        if "All Accounts" not in acc_filter:
            filtered_df = filtered_df[filtered_df["account"].isin(acc_filter)]

    st.markdown("---")
    _render_kpi_cards(filtered_df, p)

    tab_edge, tab_drill, tab_trends = st.tabs(["💎 The Bubble Vault", "🔍 Intelligent Drill-down", "📈 Performance Trends"])

    with tab_edge:
        _render_edge_bubble_vault(filtered_df, p)

    with tab_drill:
        _render_drilldown_section(filtered_df, p)

    with tab_trends:
        _render_radial_balance(filtered_df, p)
        _render_trend_chart(filtered_df, p)

# ============================================================
# 💎 NEW: The "Bubble Vault" (Packed Bubbles)
# ============================================================
def _render_edge_bubble_vault(df, p):
    st.subheader("Financial Ecosystem")
    st.caption("A dynamic view of your spending 'gravity'. Larger bubbles represent higher impact.")
    
    exp_df = df[df["type"] == "Expense"].copy()
    if exp_df.empty: return

    # We use a Scatter plot styled as a Packed Bubble chart
    # Grouping to prevent too many small bubbles
    bub_df = exp_df.groupby(["category", "payee"])["amount"].sum().reset_index()
    
    # Calculate a simple "Impact Score" for color
    max_amt = bub_df["amount"].max()
    
    fig = px.scatter(
        bub_df, x="category", y="amount", size="amount", color="category",
        hover_name="payee", size_max=60,
        color_discrete_sequence=p['categorical'],
        template="plotly_dark" if "Dark" in get_setting("theme", "Light") else "plotly_white"
    )
    
    fig.update_layout(
        showlegend=False, 
        xaxis=dict(showgrid=False, title="Categories"),
        yaxis=dict(showgrid=True, gridcolor=p['grid'], title="Total Spent"),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color=p['text'],
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 🔍 INTERACTIVE: Drill-down Bar Chart
# ============================================================
def _render_drilldown_section(df, p):
    st.subheader("Deep Dive Explorer")
    exp_df = df[df["type"] == "Expense"].copy()
    cat_grp = exp_df.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=True)

    fig = px.bar(cat_grp, x="amount", y="category", orientation='h', 
                 color="amount", color_continuous_scale=[p['blue'], p['expense']])
    
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color=p['text'])
    
    # Interactive Event
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if selected and selected.get("selection", {}).get("points"):
        selected_cat = selected["selection"]["points"][0]["y"]
        st.markdown(f"### 📋 Analysis: {selected_cat}")
        details = exp_df[exp_df["category"] == selected_cat][["date", "payee", "amount", "description"]].copy()
        details["date"] = details["date"].dt.date
        st.dataframe(details.sort_values("date", ascending=False), use_container_width=True, hide_index=True)

# ============================================================
# 🎡 NEW: Radial Balance Chart
# ============================================================
def _render_radial_balance(df, p):
    """Erstatter Polar-diagrammet med en moderne Donut-visning."""
    st.subheader("Spending Allocation")
    st.caption("Relativ fordeling mellom dine utgiftskategorier.")
    
    exp_df = df[df["type"] == "Expense"].groupby("category")["amount"].sum().reset_index()
    
    if exp_df.empty:
        st.info("Ingen data å vise.")
        return

    fig = px.pie(
        exp_df, 
        values='amount', 
        names='category', 
        hole=0.5, # Dette lager 'donut'-hullet
        color_discrete_sequence=p['categorical']
    )
    
    # Legg til tekst i midten av hullet og juster stil
    fig.update_traces(
        textinfo='percent+label',
        hoverinfo='label+value',
        marker=dict(line=dict(color=p['paper'], width=2))
    )
    
    fig.update_layout(
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        font_color=p['text'],
        margin=dict(l=20, r=20, t=20, b=20),
        annotations=[dict(text='Expenses', x=0.5, y=0.5, font_size=20, showarrow=False)]
    )
    
    st.plotly_chart(fig, use_container_width=True)
# ============================================================
# 🃏 Standard Visuals (Optimized)
# ============================================================
def _render_kpi_cards(df, p):
    inc = df[df["type"] == "Income"]["amount"].sum()
    exp = df[df["type"] == "Expense"]["amount"].sum()
    net = inc - exp
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Income", format_currency(inc))
    c2.metric("Expenses", format_currency(exp), delta=f"-{format_currency(exp)}", delta_color="inverse")
    c3.metric("Net Flow", format_currency(net))
    c4.metric("Savings", f"{(net/inc*100) if inc > 0 else 0:.1f}%")

def _render_trend_chart(df, p):
    df['month'] = df['date'].dt.to_period('M').astype(str)
    monthly = df.groupby(['month', 'type'])['amount'].sum().unstack(fill_value=0).reset_index()
    fig = go.Figure()
    if 'Expense' in monthly.columns:
        fig.add_trace(go.Scatter(x=monthly['month'], y=monthly['Expense'], name="Out", fill='tozeroy', line_color=p['expense']))
    if 'Income' in monthly.columns:
        fig.add_trace(go.Scatter(x=monthly['month'], y=monthly['Income'], name="In", line_color=p['income']))
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color=p['text'])
    st.plotly_chart(fig, use_container_width=True)