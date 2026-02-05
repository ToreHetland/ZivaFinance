# components/ui_enhancements.py
from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import Optional
from utils.ui_theme import UI_COLORS, card_style, pill_style, kpi_box
from config.config import format_currency
from config.i18n import t
from config.i18n import t
lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))


# ---------- Messaging ----------
def render_success_message(msg: str):
    st.markdown(
        f"""
        <div style="{card_style(12)};border-left:4px solid {UI_COLORS['success']}">
            ✅ {msg}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_error_message(msg: str):
    st.markdown(
        f"""
        <div style="{card_style(12)};border-left:4px solid {UI_COLORS['error']}">
            ❌ {msg}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- Banner / Intro ----------
def render_welcome_banner():
    st.markdown(
        f"""
        <div style="{card_style(18)};display:flex;align-items:center;justify-content:space-between;">
            <div>
                <div style="font-size:22px;font-weight:800">👋 {t('app_title')}</div>
                <div style="color:{UI_COLORS['muted']}">Your money, at a glance. Add expenses from the left, see insights here.</div>
            </div>
            <div style="{pill_style('info')}">Tip: Use AI Smart Entry for quick captures</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- Quick Stats ----------
def render_quick_stats(transactions_df: pd.DataFrame):
    if transactions_df.empty:
        return
    df = transactions_df.copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    income = df.query("type == 'Income'")["amount"].sum()
    expense = df.query("type == 'Expense'")["amount"].sum()
    net = income - expense
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(kpi_box(t("total_income"), format_currency(income)), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_box(t("total_expense"), format_currency(expense)), unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_box(t("net_balance"), format_currency(net)), unsafe_allow_html=True)


# ---------- Feature Highlights ----------
def render_feature_highlights():
    st.markdown(
        f"""
        <div style="{card_style(16)}">
            <div style="font-weight:700;margin-bottom:8px;">Highlights</div>
            <ul style="margin:0 0 0 18px;">
                <li>AI-powered quick entry (“Spent 250 NOK on coffee yesterday”)</li>
                <li>Budget vs Actual with sub-categories and monthly comparison</li>
                <li>Forecast & Financial Health Radar</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tip_of_the_day():
    st.markdown(
        f"""
        <div style="{card_style(16)}">
            <strong>💡 Tip:</strong> Tag recurring bills using “Recurring” so they auto-post monthly.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- Empty State ----------
def render_empty_state(icon: str, title: str, subtitle: str):
    st.markdown(
        f"""
        <div style="{card_style(22)};text-align:center;">
            <div style="font-size:40px">{icon}</div>
            <div style="font-size:20px;font-weight:800;margin-top:6px;">{title}</div>
            <div style="color:{UI_COLORS['muted']};margin-top:6px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- Progress ----------
def create_progress_bar(
    value: float, label: Optional[str] = None, color: str = UI_COLORS["primary"]
):
    value = max(0.0, min(1.0, float(value)))
    pct = f"{value*100:.0f}%"
    st.markdown(
        f"""
        <div style="{card_style(12)}">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <div style="font-weight:700">{label or 'Progress'}</div>
                <div style="font-weight:700;color:{UI_COLORS['text']}">{pct}</div>
            </div>
            <div style="width:100%;height:10px;border-radius:999px;background:{UI_COLORS['surfaceSubtle']};border:1px solid {UI_COLORS['border']}">
                <div style="height:100%;width:{pct};background:{color};border-radius:999px;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
