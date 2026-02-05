# components/settings.py
import streamlit as st
import pandas as pd

from config.config import get_setting, set_setting
from utils.backup_manager import create_automatic_backup
from core.default_translations import translate_defaults_for_user

from core.db_operations import (
    execute_query_db,
    load_data_db,
    get_all_users_admin,
    get_connection,
    hash_password,
    verify_password,
)

from config.i18n import t


def settings():
    """
    Main entry point for the Settings page.
    Consolidates user preferences + B2C self-service tools + admin tools.
    """
    # --- AUTH GUARD ---
    if not st.session_state.get("authenticated"):
        st.warning("Please log in.")
        st.stop()

    user_id = st.session_state.get("username")  # used as user_id across tables
    user_email = (st.session_state.get("email") or "").strip().lower()
    lang = (st.session_state.get("language") or "no").strip().lower()

    # --- HEADER DESIGN ---
    st.markdown(
        """
        <div style="background: linear-gradient(180deg, #ffffff 0%, #eef1f5 100%); padding: 25px; border-radius: 12px; border: 1px solid #d1d5db; margin-bottom: 25px;">
            <div style="display: flex; align-items: center;">
                <div style="background: #e0e7ff; color: #3730a3; width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: bold; margin-right: 20px; border: 2px solid #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">👤</div>
                <div>
                    <div style="font-size: 22px; font-weight: 800; color: #1f2937;">User Profile</div>
                    <div style="color: #6b7280; font-size: 14px;">Manage your Ziva experience</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- ADMIN SECTION ---
    if st.session_state.get("role") == "admin":
        with st.expander("🛡️ Admin User & License Management", expanded=False):
            render_admin_user_manager()
        st.markdown("---")

    # --- TABS ---
    tab1, tab2, tab3 = st.tabs(["🎨 Appearance", "🧠 Intelligence & Analytics", "🔧 System & Data"])

    # ==========================================
    # 1) APPEARANCE
    # ==========================================
    with tab1:
        st.subheader("Visual Preferences")
        c1, c2 = st.columns(2)

        with c1:
            current_theme = get_setting("theme", "Ziva Silver")
            theme_options = ["Ziva Silver", "Midnight Pro", "Paper White", "Nordic Blue", "Cyber Retro"]
            idx = theme_options.index(current_theme) if current_theme in theme_options else 0

            new_theme = st.selectbox("App Theme", theme_options, index=idx, key="settings_theme_select_final")
            if new_theme != current_theme:
                set_setting("theme", new_theme)
                st.toast(f"Theme set to {new_theme}.")
                st.rerun()

            st.caption(
                """
                ✨ **Ziva Silver:** Retro-modern | 🌑 **Midnight Pro:** Pro Dark Mode | 📄 **Paper White:** High Contrast  
                ❄️ **Nordic Blue:** Focused Cool Tones | 📟 **Cyber Retro:** Hacker Terminal Style
                """
            )

        with c2:
            current_name = get_setting("user_name", st.session_state.get("username", "User"))
            new_name = st.text_input("Display Name", value=current_name, key="settings_display_name_final")
            if new_name != current_name:
                set_setting("user_name", new_name)
                st.toast("Display name updated!")

        st.markdown("---")

        # ✅ LANGUAGE + REGION
        st.subheader(t("settings.language_region", lang))

        LANG_OPTIONS = {
            "Norwegian": "no",
            "Swedish": "sv",
            "Danish": "da",
            "German": "de",
            "Spanish": "es",
            "English": "en",
            "Dutch": "nl",
            "French": "fr",
            "Italian": "it",
            "Ukrainian": "uk",
        }

        current_lang = lang
        current_lang_label = next((k for k, v in LANG_OPTIONS.items() if v == current_lang), "Norwegian")

        col_l1, col_l2 = st.columns([2, 1])
        with col_l1:
            new_lang_label = st.selectbox(
                "Application language",
                options=list(LANG_OPTIONS.keys()),
                index=list(LANG_OPTIONS.keys()).index(current_lang_label),
                key="settings_language_select",
            )

        with col_l2:
            st.markdown("**Default region**")
            st.caption("Country: **NO**")
            st.caption("Currency: **NOK**")

        if st.button("Save language", type="primary", key="settings_save_language_btn", width="stretch"):
            new_lang = LANG_OPTIONS[new_lang_label]
            try:
                execute_query_db(
                    "UPDATE users SET language = :l WHERE username = :u",
                    {"l": new_lang, "u": user_id},
                )
                st.session_state.language = new_lang
                st.success("✅ Language updated.")
                st.rerun()
            except Exception as e:
                st.error(f"Language update failed: {e}")

        st.caption(
            "Note: changing language affects onboarding defaults and labels. "
            "Existing category and account names are not automatically renamed."
        )

        # ✅ Translate defaults (must be INSIDE settings())
        with st.expander("🌍 Translate my default categories & default account", expanded=False):
            st.caption(
                "This renames ONLY Ziva’s standard onboarding categories and your default account "
                "to the selected language. Your custom categories are not changed."
            )

            if st.button(
                "Translate defaults now",
                type="primary",
                key="settings_translate_defaults_btn",
                width="stretch",
            ):
                try:
                    target_lang = (st.session_state.get("language") or "no").strip().lower()
                    cat_n, acc_n = translate_defaults_for_user(user_id=user_id, target_lang=target_lang)
                    st.success(f"✅ Translation complete. Categories updated: {cat_n}, default account updated: {acc_n}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Translation failed: {e}")

    # ==========================================
    # 2) INTELLIGENCE & ANALYTICS
    # ==========================================
    with tab2:
        col_ai, col_ana = st.columns(2)

        with col_ai:
            st.subheader("🧠 AI Advisor Persona")
            st.caption("Choose how the AI talks to you.")
            persona = get_setting("ai_persona", "Professional Analyst")
            persona_opts = ["Friendly Coach", "Professional Analyst", "Strict Accountant", "Wall Street Analyst"]
            p_idx = persona_opts.index(persona) if persona in persona_opts else 1

            new_persona = st.selectbox("AI Personality", persona_opts, index=p_idx, key="settings_ai_persona_final")
            if new_persona != persona:
                set_setting("ai_persona", new_persona)
                st.toast("AI Persona updated!")

        with col_ana:
            st.subheader("📊 Analytics Settings")
            st.caption("Permanently hide specific categories from charts.")
            all_cats_df = load_data_db("categories", user_id=user_id)
            if not all_cats_df.empty:
                cat_options = sorted(all_cats_df["name"].unique().tolist())
                saved_exclusions = get_setting("analytics_excluded_categories", [])
                valid_selections = [c for c in saved_exclusions if c in cat_options]

                new_exclusions = st.multiselect(
                    "Excluded Categories",
                    options=cat_options,
                    default=valid_selections,
                    key="settings_analytics_exclude_final",
                )
                if new_exclusions != saved_exclusions:
                    set_setting("analytics_excluded_categories", new_exclusions)
                    st.toast("Analytics filter updated!")
            else:
                st.info("No categories found.")

        st.markdown("---")
        st.subheader("🔔 Alerts & Defaults")
        c3, c4 = st.columns(2)

        with c3:
            current_thresh = int(get_setting("budget_alert_threshold", 80))
            new_thresh = st.slider(
                "Budget Warning Threshold (%)",
                50,
                100,
                current_thresh,
                step=5,
                key="settings_budget_threshold_final",
            )
            if new_thresh != current_thresh:
                set_setting("budget_alert_threshold", new_thresh)

        with c4:
            acc_df = load_data_db("accounts", user_id=user_id)
            if acc_df is not None and not acc_df.empty:
                account_list = sorted(acc_df["name"].unique().tolist())
                current_def_acc = get_setting("default_account_name", account_list[0])
                idx_acc = account_list.index(current_def_acc) if current_def_acc in account_list else 0

                new_def_acc = st.selectbox(
                    "Default Account",
                    options=account_list,
                    index=idx_acc,
                    key="settings_default_account_final",
                )
                if new_def_acc != current_def_acc:
                    set_setting("default_account_name", new_def_acc)
            else:
                st.warning("No accounts found.")

    # ==========================================
    # 3) SYSTEM / DATA
    # ==========================================
    with tab3:
        st.subheader("Account & Data")

        # A) CHANGE PASSWORD
        st.markdown("### 🔐 Change password")
        with st.expander("Change password", expanded=False):
            with st.form("settings_change_password_form"):
                current_pw = st.text_input("Current password", type="password")
                new_pw = st.text_input("New password", type="password")
                new_pw2 = st.text_input("Repeat new password", type="password")
                submitted = st.form_submit_button("Update password", type="primary")

                if submitted:
                    if not current_pw or not new_pw or not new_pw2:
                        st.error("Please fill all fields.")
                    elif new_pw != new_pw2:
                        st.error("New passwords do not match.")
                    elif len(new_pw) < 8:
                        st.error("Password must be at least 8 characters.")
                    else:
                        try:
                            with get_connection() as conn:
                                row = conn.execute(
                                    "SELECT password_hash FROM users WHERE username = :u",
                                    {"u": user_id},
                                ).fetchone()

                            stored_hash = (row[0] if row else "") or ""
                            if not stored_hash:
                                st.error("Could not read password for this user.")
                            elif not verify_password(current_pw, stored_hash):
                                st.error("Current password is incorrect.")
                            else:
                                execute_query_db(
                                    "UPDATE users SET password_hash = :ph WHERE username = :u",
                                    {"ph": hash_password(new_pw), "u": user_id},
                                )
                                st.success("✅ Password updated.")
                                st.toast("Password changed")
                        except Exception as e:
                            st.error(f"Password update failed: {e}")

        # B) EXPORT DATA
        st.markdown("### 📤 Export your data")
        with st.expander("Export CSV (transactions, accounts, categories…)", expanded=False):
            st.caption("Download your data as CSV files. Useful for backup or moving to another app.")

            def _csv_bytes(df: pd.DataFrame) -> bytes:
                return df.to_csv(index=False).encode("utf-8")

            tx = load_data_db("transactions", user_id=user_id)
            acc = load_data_db("accounts", user_id=user_id)
            cat = load_data_db("categories", user_id=user_id)
            pay = load_data_db("payees", user_id=user_id)
            bud = load_data_db("budgets", user_id=user_id)
            rec = load_data_db("recurring", user_id=user_id)
            loans = load_data_db("loans", user_id=user_id)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.download_button("⬇️ Transactions CSV", data=_csv_bytes(tx), file_name="ziva_transactions.csv", mime="text/csv", width="stretch")
                st.download_button("⬇️ Accounts CSV", data=_csv_bytes(acc), file_name="ziva_accounts.csv", mime="text/csv", width="stretch")
                st.download_button("⬇️ Categories CSV", data=_csv_bytes(cat), file_name="ziva_categories.csv", mime="text/csv", width="stretch")
            with c2:
                st.download_button("⬇️ Payees CSV", data=_csv_bytes(pay), file_name="ziva_payees.csv", mime="text/csv", width="stretch")
                st.download_button("⬇️ Budgets CSV", data=_csv_bytes(bud), file_name="ziva_budgets.csv", mime="text/csv", width="stretch")
                st.download_button("⬇️ Recurring CSV", data=_csv_bytes(rec), file_name="ziva_recurring.csv", mime="text/csv", width="stretch")
            with c3:
                st.download_button("⬇️ Loans CSV", data=_csv_bytes(loans), file_name="ziva_loans.csv", mime="text/csv", width="stretch")

            st.caption("Tip: You can import these into Excel / Google Sheets.")

        st.markdown("---")

        # C) FACTORY RESET
        st.subheader("Data Management")
        st.markdown(
            """
            <div style="background:#fff1f2; border:1px solid #fda4af; padding:20px; border-radius:10px; margin-bottom:10px;">
                <h4 style="color:#be123c; margin-top:0;">⚠️ Danger Zone</h4>
                <p style="font-size:13px; color:#881337;">Resetting your data is irreversible. An automatic backup will be created before deletion.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("💣 Factory Reset (delete data, keep account)", expanded=False):
            confirm_text = st.text_input("Type 'DELETE EVERYTHING' to confirm:", key="settings_factory_reset_confirm_final")
            if st.button("Confirm Reset", type="primary", disabled=(confirm_text != "DELETE EVERYTHING"), key="settings_reset_btn_final"):
                with st.spinner("Creating safety backup..."):
                    backup_path = create_automatic_backup("pre_factory_reset")

                if backup_path:
                    try:
                        tables = ["transactions", "accounts", "budgets", "categories", "payees", "loans", "recurring"]
                        for t_name in tables:
                            execute_query_db(f"DELETE FROM {t_name} WHERE user_id = :uid", {"uid": user_id})
                        st.success("System reset complete.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Reset failed: {e}")
                else:
                    st.error("Backup failed. Reset aborted for safety.")

        # D) DELETE ACCOUNT
        st.markdown("### 🧨 Delete account")
        with st.expander("Delete my account permanently", expanded=False):
            st.warning("This will delete your user profile AND all your data. This cannot be undone.")
            st.caption("We recommend exporting your CSV first.")

            confirm_a = st.text_input("Type DELETE to confirm", key="settings_delete_account_confirm_a")
            confirm_b = st.text_input("Type your email to confirm", value="", key="settings_delete_account_confirm_b").strip().lower()

            delete_ok = (confirm_a.strip().upper() == "DELETE") and (confirm_b == user_email) and bool(user_email)

            if st.button("Delete account permanently", type="primary", disabled=not delete_ok, width="stretch"):
                with st.spinner("Creating safety backup..."):
                    backup_path = create_automatic_backup("pre_delete_account")

                if not backup_path:
                    st.error("Backup failed. Delete aborted for safety.")
                    st.stop()

                try:
                    tables = ["transactions", "accounts", "budgets", "categories", "payees", "loans", "recurring", "license_requests"]
                    for t_name in tables:
                        try:
                            execute_query_db(f"DELETE FROM {t_name} WHERE user_id = :uid", {"uid": user_id})
                        except Exception:
                            pass

                    execute_query_db("DELETE FROM users WHERE username = :u", {"u": user_id})

                    for k in list(st.session_state.keys()):
                        st.session_state.pop(k, None)

                    st.success("✅ Your account has been deleted.")
                    st.rerun()

                except Exception as e:
                    st.error(f"Account deletion failed: {e}")


def render_admin_user_manager():
    """Admin tools strictly for user and license data management."""
    users = get_all_users_admin()
    if not users:
        st.info("No users found.")
        return

    user_df = pd.DataFrame(users, columns=["Username", "Role", "License"])
    st.dataframe(user_df, width="stretch")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        user_to_reset = st.selectbox(
            "Select User to Reset",
            [u[0] for u in users if u[1] != "admin"],
            key="admin_user_reset_sel",
        )
    with col2:
        new_pass = st.text_input("New Temporary Password", type="password", key="admin_user_reset_pass")

    if st.button("Update User Password (bcrypt)", key="admin_update_pass_btn"):
        if not user_to_reset or not new_pass:
            st.error("Pick a user and enter a password.")
            return
        if len(new_pass) < 8:
            st.error("Password must be at least 8 characters.")
            return

        ok = execute_query_db(
            "UPDATE users SET password_hash = :ph WHERE username = :u",
            {"ph": hash_password(new_pass), "u": user_to_reset},
        )
        if ok:
            st.success(f"Password for {user_to_reset} updated!")
        else:
            st.error("Password update failed.")
