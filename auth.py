import streamlit as st
import datetime

from core.db_operations import (
    get_connection,
    seed_user_categories,
    execute_query_db,
    send_license_request_email,
    hash_password,
    verify_password,
    create_password_reset,
    send_password_reset_email,
    reset_password_with_token,
)

# ✅ These must exist in your project. If your module path differs,
# change core.onboarding to the correct location.
from core.onboarding import (
    ensure_user_bootstrap,
    should_show_opening_balance,
    opening_balance_dialog,
)


def get_app_base_url() -> str:
    """
    Best-effort base URL for Streamlit Cloud + local.
    Safe fallback to "".
    """
    try:
        # Streamlit 1.30+ internal context (works in many deployments)
        ctx = st.runtime.scriptrunner.get_script_run_ctx()
        if ctx and ctx.request:
            return f"{ctx.request.protocol}://{ctx.request.host}"
    except Exception:
        pass

    # Fallback
    return ""


def _get_reset_token_from_query() -> str:
    """
    Reads reset token from URL query param ?reset=<token>
    Supports both new (st.query_params) and old (st.experimental_get_query_params).
    """
    try:
        qp = st.query_params
        token = qp.get("reset", "")
        if isinstance(token, list):
            token = token[0] if token else ""
        return (token or "").strip()
    except Exception:
        pass

    try:
        qp = st.experimental_get_query_params()
        token_list = qp.get("reset", [""])
        return (token_list[0] or "").strip()
    except Exception:
        return ""


def _clear_reset_query_param():
    try:
        st.query_params.clear()
        return
    except Exception:
        pass

    try:
        st.experimental_set_query_params()
    except Exception:
        pass


def login_screen():
    # ---------------------------------------------------------
    # 🎨 Login UI (Centered + Strong branding)
    # ---------------------------------------------------------
    st.markdown(
        """
        <style>
          .ziva-auth-wrap {max-width: 460px; margin: 0 auto;}
          .ziva-auth-card {
            background: rgba(255,255,255,0.70);
            border: 1px solid rgba(148,163,184,0.25);
            border-radius: 18px;
            padding: 18px 18px 10px 18px;
            box-shadow: 0 10px 30px rgba(15,23,42,0.08);
          }
          button[data-baseweb="tab"] {padding-top: 10px; padding-bottom: 10px;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, mid, right = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<div class="ziva-auth-wrap">', unsafe_allow_html=True)
        try:
            st.image("assets/branding/Ziva_logo.png", width=240)
        except Exception:
            st.markdown("## Ziva")
        st.caption("Sign in to continue")
        st.markdown('<div class="ziva-auth-card">', unsafe_allow_html=True)

    # ---------------------------------------------------------
    # PASSWORD RESET MODE (user opens link: /?reset=<token>)
    # ---------------------------------------------------------
    reset_token = _get_reset_token_from_query()
    if reset_token:
        st.subheader("Reset your password")

        with st.form("reset_password_form"):
            new_pw = st.text_input("New password", type="password")
            new_pw2 = st.text_input("Repeat new password", type="password")
            ok = st.form_submit_button("Set new password", type="primary")

            if ok:
                if not new_pw or len(new_pw) < 8:
                    st.error("Password must be at least 8 characters.")
                elif new_pw != new_pw2:
                    st.error("Passwords do not match.")
                else:
                    success = reset_password_with_token(reset_token, new_pw)
                    if success:
                        st.success("✅ Password updated. You can now log in.")
                        _clear_reset_query_param()
                        st.rerun()
                    else:
                        st.error("Invalid or expired reset link.")

        st.caption("If your link expired, request a new reset link from the Login tab.")

        # Close HTML containers before stopping
        left, mid, right = st.columns([1, 1.2, 1])
        with mid:
            st.markdown("</div>", unsafe_allow_html=True)  # /ziva-auth-card
            st.markdown("</div>", unsafe_allow_html=True)  # /ziva-auth-wrap

        st.stop()

    tab1, tab2 = st.tabs(["Login", "Register"])

    # -------------------
    # TAB 1: LOGIN (EMAIL)
    # -------------------
    with tab1:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email").strip().lower()
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("LOGIN")

            if submit:
                if not email or not password:
                    st.warning("Please enter email and password.")
                    st.stop()

                try:
                    with get_connection() as conn:
                        cur = conn.execute(
                            """
                            SELECT username, role, full_name, language, email, password_hash
                              FROM users
                             WHERE lower(email) = :e
                            """,
                            {"e": email.strip().lower()},
                        )
                        user = cur.fetchone()

                    if not user:
                        st.error("Invalid email or password.")
                        st.stop()

                    stored_hash = user[5] or ""
                    if not verify_password(password, stored_hash):
                        st.error("Invalid email or password.")
                        st.stop()

                    # Session
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = user[0]  # internal user_id
                    st.session_state["role"] = user[1]
                    st.session_state["full_name"] = user[2]
                    st.session_state["language"] = user[3] if user[3] else "en"
                    st.session_state["email"] = user[4]

                    # Seed defaults + onboarding bootstrap
                    seed_user_categories(st.session_state["username"])
                    ensure_user_bootstrap(st.session_state["username"], st.session_state["language"])

                    # Optional opening balance (only if user has no transactions yet)
                    if should_show_opening_balance(st.session_state["username"]):
                        opening_balance_dialog(st.session_state["username"], st.session_state["language"])

                    st.success(
                        f"Welcome back, {st.session_state['full_name'] if st.session_state['full_name'] else st.session_state['email']}!"
                    )
                    st.rerun()

                except Exception as e:
                    st.error(f"Login failed: {e}")

        # -------------------
        # FORGOT PASSWORD (EMAIL RESET LINK)
        # -------------------
        st.markdown("---")
        with st.expander("Forgot password?"):
            reset_email = st.text_input("Enter your email", key="forgot_email").strip().lower()

            if st.button("Send reset link", type="primary", key="forgot_btn"):
                if not reset_email:
                    st.warning("Enter your email.")
                else:
                    reset_link = None  # ✅ prevents "referenced before assignment"

                    token = create_password_reset(reset_email)
                    if token:
                        base_url = get_app_base_url()
                        reset_link = f"{base_url}/?reset={token}" if base_url else f"?reset={token}"

                    if reset_link:
                        send_password_reset_email(reset_email, reset_link)

                    st.success("If that email exists in Ziva, a reset link has been sent.")

    # -----------------------
    # TAB 2: REGISTER (EMAIL)
    # -----------------------
    with tab2:
        st.subheader("Create New Account")
        with st.form("registration_form"):
            reg_email = st.text_input("Email").strip().lower()
            reg_full_name = st.text_input("Full Name").strip()
            reg_pass = st.text_input("Choose Password", type="password")
            reg_pass2 = st.text_input("Repeat Password", type="password")

            lang_options = {
                "English": "en",
                "Norwegian": "no",
                "Swedish": "sv",
                "Danish": "da",
                "German": "de",
                "Spanish": "es",
                "Dutch": "nl",
                "French": "fr",
                "Italian": "it",
                "Ukrainian": "uk",
            }
            reg_lang_name = st.selectbox("Preferred Language", options=list(lang_options.keys()), index=1)
            license_code = st.text_input("License Code").strip().upper()

            submit = st.form_submit_button("REGISTER")

            if submit:
                if not reg_email or not reg_pass or not reg_full_name or not license_code:
                    st.warning("Please fill in all required fields.")
                    st.stop()
                if reg_pass != reg_pass2:
                    st.warning("Passwords do not match.")
                    st.stop()
                if len(reg_pass) < 8:
                    st.warning("Password must be at least 8 characters.")
                    st.stop()

                lang_code = lang_options[reg_lang_name]
                reg_username = reg_email  # internal user_id

                try:
                    with get_connection() as conn:
                        # License must be valid + unused
                        cur = conn.execute(
                            """
                            SELECT code
                              FROM licenses
                             WHERE code = :c
                               AND is_used = false
                            """,
                            {"c": license_code},
                        )
                        if not cur.fetchone():
                            st.error("Invalid or already used License Code.")
                            st.stop()

                        # Email must not exist
                        cur = conn.execute(
                            "SELECT username FROM users WHERE lower(email) = :e",
                            {"e": reg_email},
                        )
                        if cur.fetchone():
                            st.error("An account with that email already exists.")
                            st.stop()

                        pw_hash = hash_password(reg_pass)

                        conn.execute(
                            """
                            INSERT INTO users (username, password_hash, role, license_code, full_name, email, language)
                            VALUES (:u, :p, :r, :l, :f, :e, :la)
                            """,
                            {
                                "u": reg_username,
                                "p": pw_hash,
                                "r": "tester",
                                "l": license_code,
                                "f": reg_full_name,
                                "e": reg_email,
                                "la": lang_code,
                            },
                        )

                        conn.execute(
                            """
                            UPDATE licenses
                               SET is_used = true,
                                   assigned_to = :u
                             WHERE code = :c
                            """,
                            {"u": reg_username, "c": license_code},
                        )

                    # Session
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = reg_username
                    st.session_state["full_name"] = reg_full_name
                    st.session_state["language"] = lang_code
                    st.session_state["role"] = "tester"
                    st.session_state["email"] = reg_email

                    seed_user_categories(reg_username)
                    ensure_user_bootstrap(reg_username, lang_code)

                    if should_show_opening_balance(reg_username):
                        opening_balance_dialog(reg_username, lang_code)

                    st.success("Registration successful!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Registration error: {e}")

        # --- LICENSE REQUEST ---
        st.markdown("---")
        with st.expander("🔑 Don't have a license code? Request one here"):
            with st.form("request_code_form"):
                req_name = st.text_input("Full Name")
                req_email = st.text_input("Email Address")
                req_note = st.text_area("Why would you like to test Ziva?")

                if st.form_submit_button("Request Access"):
                    n = (req_name or "").strip()
                    em = (req_email or "").strip()
                    note = (req_note or "").strip()

                    if n and em:
                        now = datetime.datetime.now()
                        execute_query_db(
                            """
                            INSERT INTO license_requests (name, email, reason, requested_at)
                            VALUES (:name, :email, :reason, :at)
                            """,
                            {"name": n, "email": em, "reason": note, "at": now},
                        )

                        success = send_license_request_email(n, em, note)
                        if success:
                            st.success("Request sent! Tore will review your request and email you a code shortly.")
                        else:
                            st.info("Request saved! Tore will review this in his Admin Panel.")
                    else:
                        st.warning("Please provide both your name and email.")

    # Close centered auth card + wrapper
    left, mid, right = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("</div>", unsafe_allow_html=True)  # /ziva-auth-card
        st.markdown("</div>", unsafe_allow_html=True)  # /ziva-auth-wrap
