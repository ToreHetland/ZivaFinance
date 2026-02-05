# components/ui_enhancements.py
from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import Optional
from config.config import format_currency
from config.i18n import t

# ---- Minimal style helpers (self-contained) ----
UI_COLORS = {
    "primary": "#4a90e2",
    "success": "#16a34a",
    "error": "#dc2626",
    "muted": "rgba(100,116,139,0.85)",
    "text": "rgba(15,23,42,0.95)",
    "surfaceSubtle": "rgba(148,163,184,0.20)",
    "border": "rgba(148,163,184,0.25)",
}

def card_style(pad: int = 14) -> str:
    return (
        f"padding:{pad}px;"
        "border-radius:16px;"
        "background:rgba(255,255,255,0.70);"
        "border:1px solid rgba(148,163,184,0.25);"
        "box-shadow:0 10px 30px rgba(15,23,42,0.08);"
    )

def pill_style(kind: str = "info") -> str:
    # Simple pill styling
    return (
        "display:inline-block;"
        "padding:6px 10px;"
        "border-radius:999px;"
        "font-size:12px;"
        "font-weight:700;"
        "background:rgba(74,144,226,0.12);"
        "border:1px solid rgba(74,144,226,0.25);"
        "color:#4a90e2;"
    )

def kpi_box(label: str, value: str) -> str:
    return f"""
    <div style="{card_style(14)}">
        <div style="font-size:12px;color:{UI_COLORS['muted']};font-weight:700;">{label}</div>
        <div style="font-size:24px;color:{UI_COLORS['text']};font-weight:900;margin-top:4px;">{value}</div>
    </div>
    """

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

# ============================================================
# 🧡 ZIVA BRANDING (Logo + Icon + Page Title)
# ============================================================

def _asset_to_base64(path: str) -> str | None:
    """Return base64 string for a local asset file, or None if missing."""
    try:
        import base64
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None

def render_ziva_brand_header(
    page_name: str,
    subtitle: str | None = None,
    *,
    icon_path: str = "assets/icons/ziva_icon.png",
    icon_size_px: int = 44,
    show_premium_badge: bool = True,
    premium_text: str | None = None,
):
    # --- Base64 icon ---
    icon_b64 = _asset_to_base64(icon_path)
    icon_html = (
        f"<img src='data:image/png;base64,{icon_b64}' "
        f"style='height:{int(icon_size_px)}px; width:auto; margin-right:10px; vertical-align:middle;'/>"
        if icon_b64 else ""
    )

    subtitle_html = (
        f"<div style='color:{UI_COLORS['muted']}; margin-top:2px; font-size:13px;'>{subtitle}</div>"
        if subtitle else ""
    )

    badge_text = premium_text or "💎 PREMIUM"
    # IMPORTANT: premium_text must be plain text (no <span> etc.)

    # --- Small CSS (badge styling) ---
    st.markdown(
        """
        <style>
          .ziva-badge{
            background: rgba(74, 144, 226, 0.10);
            color: #4A90E2;
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            border: 1px solid rgba(74, 144, 226, 0.20);
            white-space: nowrap;
            display:inline-block;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- Layout (no nested badge_html string) ---
    left, right = st.columns([8, 2])

    with left:
        st.markdown(
            f"""
            <div style="margin: 6px 0 18px 0;">
              <div style="font-size:28px;font-weight:900;letter-spacing:-0.6px;line-height:1.1;margin:0;">
                {icon_html}<span style="vertical-align:middle;">Ziva {page_name}</span>
              </div>
              {subtitle_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        if show_premium_badge:
            st.markdown(f"<div style='text-align:right;'><span class='ziva-badge'>{badge_text}</span></div>",
                        unsafe_allow_html=True)
