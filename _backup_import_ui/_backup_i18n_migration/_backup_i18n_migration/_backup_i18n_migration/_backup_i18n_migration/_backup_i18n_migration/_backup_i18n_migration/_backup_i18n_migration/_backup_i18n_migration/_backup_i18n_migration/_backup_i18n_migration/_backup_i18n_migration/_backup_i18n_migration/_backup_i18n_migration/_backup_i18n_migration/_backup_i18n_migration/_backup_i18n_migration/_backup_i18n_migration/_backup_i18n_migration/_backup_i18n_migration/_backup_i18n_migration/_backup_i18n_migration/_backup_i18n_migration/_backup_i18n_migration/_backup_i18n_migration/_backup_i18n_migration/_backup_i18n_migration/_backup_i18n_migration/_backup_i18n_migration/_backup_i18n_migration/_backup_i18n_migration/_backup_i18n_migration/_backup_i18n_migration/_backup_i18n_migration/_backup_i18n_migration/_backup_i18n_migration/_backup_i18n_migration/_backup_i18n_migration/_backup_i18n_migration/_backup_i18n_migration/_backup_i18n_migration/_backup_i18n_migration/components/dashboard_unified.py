import streamlit as st
import datetime
import uuid
import smtplib
import pandas as pd
from core.db_operations import load_data_db, execute_query_db, get_connection, send_approval_email
from core.language_manager import t, get_time_greeting_key
from utils.ziva_theme import apply_ziva_theme
from config.i18n import t
lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

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
            st.dataframe(users[display_cols], width="stretch")  # Updated for 2026
            
            col_a, col_b = st.columns(2)
            with col_a:
                user_to_del = st.selectbox("Select user to manage", users["username"], key="admin_user_select")
                if st.button("Delete User Account", type="primary", width="stretch"): # Updated
                    execute_query_db("DELETE FROM users WHERE username = :u", {"u": user_to_del})
                    st.success(f"User {user_to_del} deleted.")
                    st.rerun()
            
            with col_b:
                new_temp_pass = st.text_input("New Temporary Password", type="password")
                if st.button("Reset User Password", width="stretch"): # Updated
                    from core.db_operations import admin_reset_password
                    if admin_reset_password(user_to_del, new_temp_pass):
                        st.success(f"Password updated for {user_to_del}!")
        else:
            st.info("No users registered yet.")

    with t2:
        st.subheader("Available Licenses")
        licenses = load_data_db("licenses")
        st.dataframe(licenses, width="stretch") # Updated
        
        if st.button("Generate New License Code", width="stretch"): # Updated
            new_code = str(uuid.uuid4())[:8].upper()
            execute_query_db("INSERT INTO licenses (code, is_used) VALUES (:c, 0)", {"c": new_code})
            st.success(f"Generated: {new_code}")
            st.rerun()

    with t3:
        st.subheader("New Access Requests")
        requests = load_data_db("license_requests", user_id="bypass")
        
        if not requests.empty:
            pending = requests[requests['status'] == 'pending']
            if not pending.empty:
                st.dataframe(pending[["name", "email", "reason", "requested_at"]], width="stretch") # Updated
                
                request_map = {row['email']: row['name'] for _, row in pending.iterrows()}
                selected_email = st.selectbox("Select request to approve", list(request_map.keys()))
                
                if st.button("Approve & Send Email", type="primary", width="stretch"): # Updated
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
            if st.button("Test SMTP Settings", width="stretch"): # Updated
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
            if st.button("Check DB Integrity", width="stretch"): # Updated
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
        
        if st.button("🚀 Generate Missing Category Icons", width="stretch", type="primary"): # Updated
            from core.icon_generator import generate_and_save_icons
            with st.status("AI is crafting your bespoke icons...", expanded=True) as status:
                generate_and_save_icons()
                status.update(label="✅ Branding complete!", state="complete", expanded=False)

# ============================================================
# 🚀 UNIFIED DASHBOARD
# ============================================================
def render_dashboard_unified():
    # 1. Main Page Imports
    from components.transactions_page import render_transactions_page
    from components.budget import render_budget
    from components.charts import render_analytics_dashboard
    from components.ai_advisor import render_ai_advisor
    from components.settings import settings as render_settings
    from components.overview import render_overview

    # 2. Auxiliary Page Imports
    from components.accounts_manager import render_accounts_manager
    from components.categories import render_categories
    from components.data_management import render_data_management
    from components.loan_calculator import render_loan_calculator
    from components.email_notifications import email_notifications as render_notifications

    apply_ziva_theme()

    current_user = st.session_state.get("username", "Guest")
    user_role = st.session_state.get("role", "tester")
    greeting_base = t(get_time_greeting_key())

    # --- Header Navigation UI ---
    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
            <div>
                <h1 style='margin:0; font-weight:800; letter-spacing:-1px;'>Ziva Strategic</h1>
                <p style='color:#64748b; margin:0;'>Welcome back, <b>{current_user}</b></p>
            </div>
            <div style="text-align: right;">
                <span style="background: rgba(74, 144, 226, 0.1); color: #4A90E2; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; border: 1px solid rgba(74, 144, 226, 0.2);">
                    💎 PREMIUM • {greeting_base}
                </span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = "Overview"

    # Define icons for Nano Banana infrastructure
    nav_icons = {
        "Overview": "📊", "Transactions": "📝", "Budget": "💰", 
        "Analytics": "📈", "AI Advisor": "🤖", "Settings": "⚙️"
    }

    aux_options = ["Select...", "Accounts", "Categories", "Data", "Loan Calculator", "Notifications"]
    if user_role == "admin":
        aux_options.append("Admin Panel")

    # Layout: Top bar navigation
    c_nav, c_more = st.columns([6, 1.2])
    
    with c_nav:
        nav_cols = st.columns(len(nav_icons))
        for i, (name, icon) in enumerate(nav_icons.items()):
            is_active = st.session_state["active_tab"] == name
            # 2026 UPDATE: Replaced use_container_width=True with width="stretch"
            if nav_cols[i].button(
                f"{icon} {name}", 
                key=f"nav_{name}", 
                width="stretch", 
                type="primary" if is_active else "secondary"
            ):
                st.session_state["active_tab"] = name
                st.rerun()

    with c_more:
        try:
            cur_ix = aux_options.index(st.session_state["active_tab"])
        except: 
            cur_ix = 0
        
        selection = st.selectbox(
            "More", 
            options=aux_options, 
            index=cur_ix, 
            label_visibility="collapsed", 
            key="dropdown_nav"
        )
        
        if selection != "Select..." and selection != st.session_state["active_tab"]:
            st.session_state["active_tab"] = selection
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Router ---
    tab = st.session_state.get("active_tab", "Overview")
    
    if tab == "Overview": 
        render_glass_card(render_overview)
    elif tab == "Transactions": 
        # Transactions page handles its own layout
        render_transactions_page()
    elif tab == "Budget": 
        render_glass_card(render_budget)
    elif tab == "Analytics": 
        render_glass_card(render_analytics_dashboard)
    elif tab == "AI Advisor": 
        st.info("🎙️ Gemini Live is ready. Speak to your data on the mobile app.")
        render_glass_card(render_ai_advisor)
    elif tab == "Settings": 
        render_glass_card(render_settings)
    elif tab == "Accounts": 
        render_glass_card(render_accounts_manager)
    elif tab == "Categories": 
        render_glass_card(render_categories)
    elif tab == "Data": 
        render_glass_card(render_data_management)
    elif tab == "Loan Calculator": 
        render_glass_card(render_loan_calculator)
    elif tab == "Notifications": 
        render_glass_card(render_notifications)
    elif tab == "Admin Panel" and user_role == "admin": 
        render_glass_card(render_admin_panel)
    else: 
        st.error(f"Page not found: {tab}")