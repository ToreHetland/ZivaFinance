from __future__ import annotations

import datetime
import smtplib
import uuid

import pandas as pd
import streamlit as st

from core.db_operations import load_data_db, execute_query_db, get_connection

# ============================================================
# OPTIONAL EMAIL SENDER (won’t crash if missing)
# ============================================================
try:
    from core.db_operations import send_approval_email
except ImportError:
    def send_approval_email(*args, **kwargs):
        return False

from core.language_manager import t, get_time_greeting
from utils.ziva_theme import apply_ziva_theme
from components.ui_enhancements import render_ziva_brand_header



def _normalize_tab_key(tab: str) -> str:
    """Accepts legacy English values and returns the new language-neutral key."""
    if not tab:
        return "overview"
    x = tab.strip().lower()

    legacy = {
        "overview": "overview",
        "transactions": "transactions",
        "budget": "budget",
        "analytics": "analytics",
        "ai advisor": "ai_advisor",
        "settings": "settings",
        "accounts": "accounts",
        "categories": "categories",
        "data": "data",
        "loan calculator": "loan_calculator",
        "notifications": "notifications",
        "admin panel": "admin_panel",

        # if someone stored title-style:
        "ai_advisor": "ai_advisor",
        "loan_calculator": "loan_calculator",
        "admin_panel": "admin_panel",
    }
    return legacy.get(x, x)
# ==========================================
# 💎 PREMIUM UI WRAPPER
# ==========================================
def render_glass_card(content_func, *args, title=None, **kwargs):
    """Wraps any Streamlit component in a translucent frosted-glass container."""
    st.markdown('<div class="ziva-card">', unsafe_allow_html=True)
    if title:
        st.markdown(f"### {title}")
    content_func(*args, **kwargs)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 🛡️ ADMIN PANEL
# ==========================================
def render_admin_panel():
    st.title(f"🛡️ {t('admin_panel')}")
    t1, t2, t3, t4 = st.tabs(["User Management", "License Keys", "Pending Requests", "Diagnostics"])
    
    with t1:
        st.subheader("Registered Testers")
        users = load_data_db("users")
        if not users.empty:
            display_cols = [c for c in ["username", "full_name", "email", "role"] if c in users.columns]
            # FIXED: width="stretch" -> use_container_width=True
            st.dataframe(users[display_cols], use_container_width=True)
            
            col_a, col_b = st.columns(2)
            with col_a:
                user_to_del = st.selectbox("Select user to manage", users["username"], key="admin_user_select")
                # FIXED: width="stretch" -> use_container_width=True
                if st.button("Delete User Account", type="primary", use_container_width=True): 
                    execute_query_db("DELETE FROM users WHERE username = :u", {"u": user_to_del})
                    st.success(f"User {user_to_del} deleted.")
                    st.rerun()
            
            with col_b:
                new_temp_pass = st.text_input("New Temporary Password", type="password")
                if st.button("Reset User Password", use_container_width=True): 
                    from core.db_operations import admin_reset_password
                    if admin_reset_password(user_to_del, new_temp_pass):
                        st.success(f"Password updated for {user_to_del}!")
        else:
            st.info("No users registered yet.")

    with t2:
            st.subheader("Available Licenses")
            
            # 1. Fetch data
            licenses = load_data_db("licenses")
            
            # 2. Show a quick summary
            if not licenses.empty:
                # Use 'is_used == False' for Postgres/Supabase compatibility
                unused_count = len(licenses[licenses['is_used'] == False])
                st.metric("Unused Keys Available", unused_count)
                st.dataframe(licenses, use_container_width=True)
            else:
                st.info("No licenses found in the database.")
            
            # 3. FIXED SQL: Use 'false' instead of '0' for Postgres compatibility
            if st.button("🚀 Generate New License Code", use_container_width=True, type="primary"): 
                new_code = f"ZIVA-{str(uuid.uuid4())[:8].upper()}"
                try:
                    execute_query_db(
                        "INSERT INTO licenses (code, is_used) VALUES (:c, false)", 
                        {"c": new_code}
                    )
                    st.success(f"Successfully generated: {new_code}")
                    # Short delay to let the DB catch up
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate license: {e}")

    with t3:
        st.subheader("New Access Requests")
        requests = load_data_db("license_requests", user_id="bypass")
        
        if not requests.empty:
            pending = requests[requests['status'] == 'pending']
            if not pending.empty:
                st.dataframe(pending[["name", "email", "reason", "requested_at"]], use_container_width=True)
                
                request_map = {row['email']: row['name'] for _, row in pending.iterrows()}
                selected_email = st.selectbox("Select request to approve", list(request_map.keys()))
                
                if st.button("Approve & Send Email", type="primary", use_container_width=True): 
                    with get_connection() as conn:
                        cur = conn.execute("SELECT code FROM licenses WHERE is_used = 0 LIMIT 1")
                        row = cur.fetchone()
                        
                        if row:
                            assigned_code = row[0]
                            selected_name = request_map[selected_email]
                            
                            with st.spinner("Using Database SMTP Settings..."):
                                if send_approval_email(selected_email, selected_name, assigned_code):
                                    conn.execute("UPDATE license_requests SET status = 'approved' WHERE email = :e", {"e": selected_email})
                                    conn.execute("UPDATE licenses SET is_used = 1 WHERE code = :c", {"c": assigned_code})
                                    st.success(f"✅ Code {assigned_code} sent to {selected_email}.")
                                    st.rerun()
                                else:
                                    st.error("Auth Failed: Check SMTP settings.")
                        else:
                            st.error("No license codes available.")
            else:
                st.success("No pending requests.")
        else:
            st.info("No requests found.")

    with t4:
        st.subheader("System Health & AI Maintenance")
        diag_c1, diag_c2 = st.columns(2)
        
        with diag_c1:
            st.markdown("#### 📧 Email System")
            if st.button("Test SMTP Settings", use_container_width=True): 
                with st.spinner("Testing..."):
                    settings_df = load_data_db("email_settings")
                    if not settings_df.empty:
                        s = settings_df.iloc[0]
                        try:
                            server = smtplib.SMTP(s["smtp_server"], int(s["smtp_port"]))
                            server.starttls()
                            server.login(s["email_address"], s["email_password"])
                            server.quit()
                            st.success(f"✅ SMTP Connected: {s['email_address']}")
                        except Exception as e:
                            st.error(f"❌ SMTP Error: {e}")
                    else:
                        st.warning("No email settings found.")

        with diag_c2:
            st.markdown("#### 📂 Database")
            if st.button("Check DB Integrity", use_container_width=True): 
                try:
                    from core.db_operations import IS_POSTGRES
                    with get_connection() as conn:
                        if IS_POSTGRES:
                            query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
                        else:
                            query = "SELECT name FROM sqlite_master WHERE type='table';"
                        res = conn.execute(query).fetchall()
                    st.success(f"✅ Connected. Found {len(res)} tables.")
                except Exception as e:
                    st.error(f"❌ Database Error: {e}")

        st.markdown("---")
        
        # --- AI BRANDING SECTION ---
        st.markdown("#### 🎨 Nano Banana Asset Generation")
        st.info("Generate custom 3D Glassmorphism icons for categories.")
        
        if st.button("🚀 Generate Missing Category Icons", use_container_width=True, type="primary"):
            try:
                from core.icon_generator import generate_and_save_icons
                with st.status("AI is crafting your bespoke icons...", expanded=True) as status:
                    generate_and_save_icons()
                    status.update(label="✅ Branding complete!", state="complete", expanded=False)
            except ImportError:
                st.error("Icon generator module not found.")

# ============================================================
# 🚀 UNIFIED DASHBOARD
# ============================================================
def render_dashboard_unified():
    # 1. Main Page Imports
    from components.transactions_page import render_transactions_page
    from components.budget import render_budget
    from components.charts import render_analytics_dashboard
    try:
        from components.ai_advisor import render_ai_advisor
    except Exception as e:
        def render_ai_advisor():
            import streamlit as st
            st.header("🤖 AI Advisor")
            st.error("AI Advisor failed to load.")
            st.code(str(e))


    from components.settings import settings as render_settings
    from components.overview import render_overview

    # 2. Auxiliary Page Imports
    from components.accounts_manager import render_accounts_manager
    from components.categories import render_categories
    from components.data_management import render_data_management
    from components.loan_calculator import render_loan_calculator
    from components.email_notifications import email_notifications as render_notifications

    apply_ziva_theme()

    current_user = (
    st.session_state.get("full_name")
    or st.session_state.get("display_name")
    or st.session_state.get("username")
    or "Guest"
)

    user_role = st.session_state.get("role", "tester")

    # ----------------------------------------------------------
    # ✅ Use language-neutral keys for state ("overview", etc.)
    # ----------------------------------------------------------
    legacy_map = {
        "Overview": "overview",
        "Transactions": "transactions",
        "Budget": "budget",
        "Analytics": "analytics",
        "AI Advisor": "ai_advisor",
        "Settings": "settings",
        "Accounts": "accounts",
        "Categories": "categories",
        "Data": "data",
        "Loan Calculator": "loan_calculator",
        "Notifications": "notifications",
        "Admin Panel": "admin_panel",
        "Select...": "select",
    }

    def _normalize_tab_key(v: str) -> str:
        if not v:
            return "overview"
        if v in legacy_map:
            return legacy_map[v]
        return v.strip().lower().replace(" ", "_")

    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = _normalize_tab_key(st.session_state.get("nav_page", "overview"))
    else:
        st.session_state["active_tab"] = _normalize_tab_key(st.session_state["active_tab"])

    active_tab = st.session_state.get("active_tab", "overview")

    # ----------------------------------------------------------
    # ✅ Header (translated title + translated welcome + greeting)
    # ----------------------------------------------------------
    page_title = t(active_tab)
    greeting_text = get_time_greeting()  # already translated string
    render_ziva_brand_header(
        page_name=page_title,
        subtitle=t("welcome_back", name=current_user),
        icon_size_px=52,
        show_premium_badge=True,
        premium_text=f"💎 PREMIUM • {greeting_text}",
    )

    # ----------------------------------------------------------
    # ✅ Top navigation (translated labels; keys in state)
    # ----------------------------------------------------------
    nav_icons = {
        "overview": "📊",
        "transactions": "📝",
        "budget": "💰",
        "analytics": "📈",
        "ai_advisor": "🤖",
        "settings": "⚙️",
    }

    aux_keys = ["select", "accounts", "categories", "data", "loan_calculator", "notifications"]
    if user_role == "admin":
        aux_keys.append("admin_panel")

    c_nav, c_more = st.columns([6, 1.2])

    with c_nav:
        nav_cols = st.columns(len(nav_icons))
        for i, (key, icon) in enumerate(nav_icons.items()):
            is_active = (active_tab == key)
            label = f"{icon} {t(key)}"
            if nav_cols[i].button(
                label,
                key=f"nav_{key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["active_tab"] = key
                st.session_state["dropdown_nav"] = "select"
                st.rerun()

    with c_more:
        if "dropdown_nav" not in st.session_state:
            st.session_state["dropdown_nav"] = "select"
        st.session_state["dropdown_nav"] = _normalize_tab_key(st.session_state["dropdown_nav"])

        def _fmt_dropdown(k: str) -> str:
            return t("select") if k == "select" else t(k)

        def _on_more_nav_change():
            sel = _normalize_tab_key(st.session_state.get("dropdown_nav", "select"))
            if sel != "select":
                st.session_state["active_tab"] = sel

        selection = st.selectbox(
            "More",
            options=aux_keys,
            format_func=_fmt_dropdown,
            index=aux_keys.index(st.session_state.get("dropdown_nav", "select")),
            label_visibility="collapsed",
            key="dropdown_nav",
            on_change=_on_more_nav_change,
        )

        # If user picked an aux option, rerun to render it
        if selection != "select" and selection != active_tab:
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ----------------------------------------------------------
    # ✅ Router (keys only)
    # ----------------------------------------------------------
    tab = st.session_state.get("active_tab", "overview")

    if tab == "overview":
        render_glass_card(render_overview)
    elif tab == "transactions":
        render_transactions_page()
    elif tab == "budget":
        render_glass_card(render_budget)
    elif tab == "analytics":
        render_glass_card(render_analytics_dashboard)
    elif tab == "ai_advisor":
        st.info("🎙️ Gemini Live is ready. Speak to your data on the mobile app.")
        render_glass_card(render_ai_advisor)
    elif tab == "settings":
        render_glass_card(render_settings)
    elif tab == "accounts":
        render_glass_card(render_accounts_manager)
    elif tab == "categories":
        render_glass_card(render_categories)
    elif tab == "data":
        render_glass_card(render_data_management)
    elif tab == "loan_calculator":
        render_glass_card(render_loan_calculator)
    elif tab == "notifications":
        render_glass_card(render_notifications)
    elif tab == "admin_panel" and user_role == "admin":
        render_glass_card(render_admin_panel)
    else:
        st.error(f"Page not found: {tab}")
