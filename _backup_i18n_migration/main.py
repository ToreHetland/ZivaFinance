# main.py
import os
from datetime import datetime
from pathlib import Path
import streamlit as st
from config.i18n import t

# Keep noisy gRPC logs quiet
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_LOG_SEVERITY_THRESHOLD"] = "ERROR"

# -------------------------------------------------------------------
# Streamlit page config (MUST be absolute first)
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Ziva",
    page_icon="assets/icons/ziva_icon.png",
    layout="wide",
)

# -------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------
from config.config import get_setting, load_config
from auth import login_screen
from utils.ziva_theme import apply_ziva_theme

# ==========================================
# 💳 SUBSCRIPTION & PAYMENT UI
# ==========================================
def render_payment_page():
    """Displayed when a user is authenticated but has no active subscription."""
    st.markdown("""
        <div style="text-align: center; padding: 50px;">
            <h1 style="font-size: 50px;">💳</h1>
            <h2 style="color: #1e40af;">Subscription Required</h2>
            <p style="color: #64748b; font-size: 18px;">
                To access Ziva's premium AI Advisor, VEO video milestones, and 
                advanced analytics, please choose a plan.
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.subheader("Premium Monthly")
            st.write("✓ Unlimited AI Strategic Advice")
            st.write("✓ Real-time Budget Audits")
            st.write("✓ Custom AI Category Icons")
            st.markdown("### 199 NOK <small>/ month</small>", unsafe_allow_html=True)
            
            if st.button("🚀 Upgrade to Premium", use_container_width=True, type="primary"):
                st.info("Redirecting to Stripe...")
                # Logic: webbrowser.open("your_stripe_link")

# ==========================================
# 🚀 MAIN APPLICATION LOGIC
# ==========================================
def main() -> None:
    # 1. Load config
    load_config()

    # 2. Session defaults (Initialization)
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    
    if "theme" not in st.session_state:
        st.session_state["theme"] = get_setting("theme", "Ziva Silver")

    # 3. Handle Authentication Logic
    if not st.session_state["authenticated"]:
        st.markdown(
            """
            <style>
              [data-testid="stSidebar"], header, footer, [data-testid="stToolbar"] { display: none !important; }
              div.block-container { padding-top: 5rem !important; max-width: 600px; margin: auto; }
            </style>
            """,
            unsafe_allow_html=True,
        )
        login_screen()
        return

# 4. SUBSCRIPTION GATEKEEPER (COMMENTED OUT - ALL USERS GET ACCESS)
    _ = """
    # Ensure isolation: check the specific expiry for the logged-in user
    expiry = st.session_state.get("subscription_end_date")
    
    # Standardize format (Postgres usually returns datetime objects, but backup just in case)
    if isinstance(expiry, str):
        try:
            expiry = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
        except:
            expiry = None

    if not expiry or datetime.now() > expiry:
        # Hide sidebar/UI elements for unpaid users
        st.markdown("<style>[data-testid='stSidebar'], [data-testid='collapsedControl'] { display: none !important; }</style>", unsafe_allow_html=True)
        render_payment_page()
        st.stop() # CRITICAL: Prevents any dashboard code from executing
    """

    # 5. Authenticated & Paid View
    apply_ziva_theme()
    
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] { display: none !important; }
          [data-testid="collapsedControl"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 6. Execute Unified Dashboard
    from components.dashboard_unified import render_dashboard_unified
    render_dashboard_unified()

if __name__ == "__main__":
    main()