# utils/ziva_theme.py
from __future__ import annotations
import streamlit as st

def apply_ziva_theme() -> None:
    """
    Applies the 'Retro-Modern / Skeuomorphic' Desktop UI Theme.
    Focus: High density, glossy gradients, visible borders, and speed.
    """
    
    # ------------------------------------------------------------
    # Retro-Modern Palette (Glossy, Metallic, Dense)
    # ------------------------------------------------------------
    # Using a "Silver/Aero" inspired palette
    bg = "#eef1f5"              # Light metallic background
    surface = "#ffffff"         # Pure white for papers/cards
    surface_alt = "#f0f2f5"     # Slightly darker for headers
    text = "#1a1a1a"            # High contrast dark grey
    
    # borders
    border_light = "#d1d5db"    # Standard container border
    border_dark = "#9ca3af"     # Button borders
    
    # Accents (Glossy Blue)
    primary_grad_top = "#4a90e2"
    primary_grad_bot = "#357abd"
    
    # ------------------------------------------------------------
    # Inject CSS
    # ------------------------------------------------------------
    st.markdown(
        f"""
        <style>
        /* ============================================================
           GLOBAL VARIABLES & FONTS
           ============================================================ */
        :root {{
            --z-bg: {bg};
            --z-surface: {surface};
            --z-text: {text};
        }}

        /* Use dense, system fonts for that "Power User" feel */
        .stApp {{
            background-color: var(--z-bg);
            font-family: 'Segoe UI', 'Verdana', sans-serif;
            font-size: 14px; 
            color: #222;
        }}
        
        /* Reduce padding everywhere for high density */
        .block-container {{
            padding-top: 1rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }}

        /* ============================================================
           THE "RIBBON" TOOLBAR BUTTONS (Glossy & Bevelled)
           ============================================================ */
        
        div[data-testid="stButton"] > button {{
            height: 60px !important; 
            width: 100% !important;
            
            /* The Retro Glossy Look */
            background: linear-gradient(to bottom, #ffffff 0%, #f0f0f0 45%, #e0e0e0 50%, #d8d8d8 100%) !important;
            border: 1px solid #999 !important;
            border-radius: 6px !important; /* Tighter radius */
            
            color: #333 !important;
            font-weight: 700 !important;
            font-size: 12px !important;
            text-transform: uppercase;
            
            box-shadow: 0 1px 2px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.8) !important;
            transition: all 0.1s ease !important;
            
            /* Layout icon above text if possible, otherwise inline */
            display: flex !important;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            line-height: 1.2 !important;
        }}

        /* Hover: Make it look brighter */
        div[data-testid="stButton"] > button:hover {{
            background: linear-gradient(to bottom, #ffffff 0%, #f8f8f8 45%, #eeeeee 50%, #e6e6e6 100%) !important;
            border-color: #666 !important;
            transform: translateY(0px); /* No movement, just color change */
        }}

        /* Active/Primary Tab: Blue Glossy Look */
        div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"] {{
            background: linear-gradient(to bottom, #6fa8dc 0%, #4a90e2 50%, #357abd 100%) !important;
            color: white !important;
            border: 1px solid #205081 !important;
            text-shadow: 0 1px 1px rgba(0,0,0,0.4);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.4), 0 2px 3px rgba(0,0,0,0.2) !important;
        }}

        /* ============================================================
           INPUTS & FORMS (Inset, Windows-style)
           ============================================================ */
        
        .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div {{
            background-color: #fff !important;
            border: 1px solid #a0a0a0 !important;
            border-top-color: #888 !important; /* Slightly darker top for depth */
            border-radius: 4px !important;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.05) !important; /* Inner shadow */
            height: 40px !important; /* Compact */
            color: #000 !important;
        }}

        /* Labels */
        .stTextInput label, .stNumberInput label, .stSelectbox label {{
            font-weight: 700;
            color: #444;
            font-size: 12px;
            margin-bottom: 4px;
        }}

        /* ============================================================
           DATA GRIDS (Excel Style)
           ============================================================ */
        
        div[data-testid="stDataFrame"] {{
            border: 1px solid #999 !important;
            background: #fff;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        
        /* Header cells */
        div[data-testid="stDataFrame"] th {{
            background: linear-gradient(to bottom, #f8f9fa, #e9ecef) !important;
            border-bottom: 2px solid #ccc !important;
            color: #333 !important;
            font-weight: bold !important;
        }}

        /* ============================================================
           CONTAINERS ("Windows")
           ============================================================ */
        
        /* The main "Paper" sheet */
        .ziva-main-panel {{
            background: white;
            border: 1px solid #bbb;
            border-radius: 6px;
            padding: 20px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
            margin-top: 10px;
        }}

        /* The Sidebar Panel (Left) */
        .ziva-sidebar-panel {{
            background: linear-gradient(to bottom, #f9f9f9, #eff1f3);
            border: 1px solid #bbb;
            border-radius: 6px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        
        /* Section Headers */
        h1, h2, h3 {{
            font-family: 'Verdana', sans-serif;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: #2c3e50;
            text-shadow: 1px 1px 0 #fff;
        }}

        </style>
        """,
        unsafe_allow_html=True
    )