# utils/ziva_theme.py
from __future__ import annotations
import streamlit as st
from config.config import get_setting

def apply_ziva_theme() -> None:
    """
    Applies the selected 'Retro-Modern' Desktop UI Theme with Glassmorphism support.
    """
    # 1. Branding: Logo and Sidebar
    # Assuming ziva_icon.png is in assets/icons/
    #try:
     #   st.logo("assets/icons/ziva_icon.png", size="large", link="https://ziva.ai")
    #except:
     #   pass

    # 2. Get current theme from database (defaults to Ziva Silver)
    current_theme = get_setting("theme", "Ziva Silver")

    # 3. Define Theme Variations
    themes = {
        "Ziva Silver": {
            "bg": "#eef1f5",
            "text": "#1a1a1a",
            "card_bg": "rgba(255, 255, 255, 0.7)", # Translucent for Glassmorphism
            "sidebar_bg": "#f8f9fa",
            "border": "rgba(187, 187, 187, 0.3)",
            "primary_btn": "linear-gradient(135deg, #6fa8dc 0%, #357abd 100%)",
            "primary_text": "white",
            "secondary_btn": "rgba(255, 255, 255, 0.8)",
            "secondary_text": "#333",
            "accent": "#4a90e2"
        },
        "Midnight Pro": {
            "bg": "#0f172a",
            "text": "#e2e8f0",
            "card_bg": "rgba(30, 41, 59, 0.7)",
            "sidebar_bg": "#0f172a",
            "border": "rgba(51, 65, 85, 0.5)",
            "primary_btn": "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
            "primary_text": "white",
            "secondary_btn": "rgba(30, 41, 59, 0.5)",
            "secondary_text": "#94a3b8",
            "accent": "#3b82f6"
        },
        "Nordic Blue": {
            "bg": "#d8dee9",
            "text": "#2e3440",
            "card_bg": "rgba(236, 239, 244, 0.7)",
            "sidebar_bg": "#e5e9f0",
            "border": "rgba(136, 192, 208, 0.4)",
            "primary_btn": "linear-gradient(135deg, #88c0d0 0%, #5e81ac 100%)",
            "primary_text": "#2e3440",
            "secondary_btn": "rgba(229, 233, 240, 0.6)",
            "secondary_text": "#4c566a",
            "accent": "#81a1c1"
        }
    }

    t = themes.get(current_theme, themes["Ziva Silver"])

    # 4. Inject Premium CSS
    st.markdown(
        f"""
        <style>
        /* ============================================================
           GLASSMORPHISM & LAYOUT
           ============================================================ */
        .stApp {{
            background-color: {t['bg']};
            background-image: radial-gradient(at 0% 0%, {t['bg']} 0px, transparent 50%), 
                              radial-gradient(at 50% 0%, {t['accent']}22 0px, transparent 50%);
            font-family: 'Segoe UI', sans-serif;
            color: {t['text']};
        }}

        /* Glassmorphism Card Utility */
        .ziva-card {{
            background: {t['card_bg']} !important;
            backdrop-filter: blur(12px) saturate(180%) !important;
            -webkit-backdrop-filter: blur(12px) saturate(180%) !important;
            border-radius: 12px !important;
            border: 1px solid {t['border']} !important;
            padding: 20px !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1) !important;
            margin-bottom: 20px !important;
        }}

        .block-container {{
            padding-top: 4rem !important;
            max-width: 95% !important;
        }}

        /* ============================================================
           BUTTONS
           ============================================================ */
        button[kind="primary"] {{
            background: {t['primary_btn']} !important;
            border: none !important;
            border-radius: 8px !important;
            color: {t['primary_text']} !important;
            font-weight: 700 !important;
            height: 42px !important;
            transition: transform 0.1s ease, box-shadow 0.1s ease !important;
        }}
        
        button[kind="primary"]:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px {t['accent']}44 !important;
        }}

        button[kind="secondary"] {{
            background: {t['secondary_btn']} !important;
            backdrop-filter: blur(4px) !important;
            border: 1px solid {t['border']} !important;
            color: {t['secondary_text']} !important;
            border-radius: 8px !important;
        }}

        /* ============================================================
           SIDEBAR & LOGO
           ============================================================ */
        [data-testid="stSidebarNav"] {{
            background-color: {t['sidebar_bg']} !important;
        }}
        
        /* Premium sidebar cards */
        .ziva-sidebar-card {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 10px;
            border: 1px solid {t['border']};
            margin-bottom: 10px;
        }}

        /* ============================================================
           INPUTS & DATA TABLES
           ============================================================ */
        .stTextInput input, .stSelectbox [data-baseweb="select"] {{
            background-color: rgba(255,255,255,0.05) !important;
            border-radius: 8px !important;
            border: 1px solid {t['border']} !important;
        }}

        /* Metrics Glass Styling */
        [data-testid="stMetricValue"] {{
            font-weight: 800 !important;
            color: {t['accent']} !important;
        }}
        
        h1, h2, h3 {{
            font-weight: 800 !important;
            letter-spacing: -0.5px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )