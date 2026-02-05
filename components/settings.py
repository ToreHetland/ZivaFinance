# components/settings.py
from __future__ import annotations

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

# NOTE:
# You currently import t() from config.i18n. This rewrite assumes:
# - t(key) returns a translated string OR returns the key itself if missing.
from config.i18n import t


# --- 1. DEFINE ALL USER TABLES (For Exports & Resets) ---
ALL_USER_TABLES = [
    "transactions",
    "accounts",
    "categories",
    "payees",
    "budgets",
    "recurring",
    "loans",
    "license_requests",
    "loan_extra_payments",
    "loan_terms_history",
]


# ---------- Small helpers ----------
def tr(key: str, default: str) -> str:
    """Translate with a safe default if key isn't defined."""
    try:
        s = t(key)
        return default if (not s or s == key) else s
    except Exception:
        return default


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return (df if df is not None else pd.DataFrame()).to_csv(index=False).encode("utf-8")


def settings():
    """
    Main entry point for the Settings page.
    Consolidates user preferences + self-service tools + admin tools.
    Fully i18n-ready (fallbacks to English defaults if keys are missing).
    """
    # --- AUTH GUARD ---
    if not st.session_state.get("authenticated"):
        st.warning(tr("settings_login_required", "Please log in."))
        st.stop()

    user_id = st.session_state.get("username")  # used as user_id across tables
    user_email = (st.session_state.get("email") or "").strip().lower()
    lang = (st.session_state.get("language") or "no").strip().lower()

    # --- HEADER DESIGN ---
    st.markdown(
        f"""
        <div style="background: linear-gradient(180deg, #ffffff 0%, #eef1f5 100%); padding: 25px; border-radius: 12px; border: 1px solid #d1d5db; margin-bottom: 25px;">
            <div style="display: flex; align-items: center;">
                <div style="background: #e0e7ff; color: #3730a3; width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: bold; margin-right: 20px; border: 2px solid #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">👤</div>
                <div>
                    <div style="font-size: 22px; font-weight: 800; color: #1f2937;">{tr("settings_user_profile", "User Profile")}</div>
                    <div style="color: #6b7280; font-size: 14px;">{tr("settings_manage_experience", "Manage your Ziva experience")}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- ADMIN SECTION ---
    if st.session_state.get("role") == "admin":
        with st.expander(tr("settings_admin_tools", "🛡️ Admin User & License Management"), expanded=False):
            render_admin_user_manager()
        st.markdown("---")

    # --- TABS ---
    tab1, tab2, tab3 = st.tabs(
        [
            f"🎨 {tr('settings_tab_appearance', 'Appearance')}",
            f"🧠 {tr('settings_tab_intelligence', 'Intelligence & Analytics')}",
            f"🔧 {tr('settings_tab_system', 'System & Data')}",
        ]
    )

    # ==========================================
    # 1) APPEARANCE
    # ==========================================
    with tab1:
        st.subheader(tr("settings_visual_preferences", "Visual Preferences"))

        c1, c2 = st.columns(2)

        # --- THEME ---
        with c1:
            current_theme = get_setting("theme", "Ziva Silver")
            theme_options = ["Ziva Silver", "Midnight Pro", "Paper White", "Nordic Blue", "Cyber Retro"]
            idx = theme_options.index(current_theme) if current_theme in theme_options else 0

            new_theme = st.selectbox(
                tr("settings_app_theme", "App Theme"),
                theme_options,
                index=idx,
                key="settings_theme_select_final",
            )
            if new_theme != current_theme:
                set_setting("theme", new_theme)
                st.toast(f"{tr('settings_theme_set_to', 'Theme set to')} {new_theme}.")
                st.rerun()

            st.caption(
                tr(
                    "settings_theme_caption",
                    "✨ **Ziva Silver:** Retro-modern | 🌑 **Midnight Pro:** Pro Dark Mode | 📄 **Paper White:** High Contrast  \n"
                    "❄️ **Nordic Blue:** Focused Cool Tones | 📟 **Cyber Retro:** Hacker Terminal Style",
                )
            )

        # --- DISPLAY NAME ---
        with c2:
            current_name = get_setting("user_name", st.session_state.get("username", "User"))
            new_name = st.text_input(
                tr("settings_display_name", "Display Name"),
                value=current_name,
                key="settings_display_name_final",
            )
            if new_name != current_name:
                set_setting("user_name", new_name)
                st.toast(tr("settings_display_name_updated", "Display name updated!"))

        st.markdown("---")

        # --- LANGUAGE + REGION ---
        LANG_OPTIONS = {
            "Norwegian (Bokmål)": "no",
            "English": "en",
            "Swedish": "sv",
            "Danish": "da",
            "German": "de",
            "Spanish": "es",
            "Dutch": "nl",
            "French": "fr",
            "Italian": "it",
            "Ukrainian": "uk",
        }

        current_lang = (st.session_state.get("language") or lang or "no").strip().lower()
        if current_lang not in set(LANG_OPTIONS.values()):
            current_lang = "no"

        label_by_code = {v: k for k, v in LANG_OPTIONS.items()}
        current_lang_label = label_by_code.get(current_lang, "Norwegian (Bokmål)")

        col_l1, col_l2 = st.columns([2, 1])

        with col_l1:
            st.subheader(tr("settings_language", "Language"))
            new_lang_label = st.selectbox(
                tr("settings_application_language", "Application language"),
                options=list(LANG_OPTIONS.keys()),
                index=list(LANG_OPTIONS.keys()).index(current_lang_label),
                key="settings_language_select",
            )

        with col_l2:
            st.markdown(f"**{tr('settings_default_region', 'Default region')}**")
            st.caption(f"{tr('settings_country', 'Country')}: **NO**")
            st.caption(f"{tr('settings_currency', 'Currency')}: **NOK**")

        new_lang = LANG_OPTIONS[new_lang_label]

        # Save immediately when changed
        if new_lang != current_lang:
            try:
                execute_query_db(
                    "UPDATE users SET language = :l WHERE username = :u",
                    {"l": new_lang, "u": user_id},
                )
                st.session_state["language"] = new_lang
                st.toast(tr("settings_language_updated", "✅ Language updated."))
                st.rerun()
            except Exception as e:
                st.error(f"{tr('settings_language_update_failed', 'Language update failed')}: {e}")

        st.caption(
            tr(
                "settings_language_note",
                "Note: changing language affects onboarding defaults and labels. "
                "Existing category and account names are not automatically renamed.",
            )
        )

        # Translate defaults
        with st.expander(
            tr("settings_translate_defaults_title", "🌍 Translate my default categories & default account"),
            expanded=False,
        ):
            st.caption(
                tr(
                    "settings_translate_defaults_desc",
                    "This renames ONLY Ziva’s standard onboarding categories and your default account "
                    "to the selected language. Your custom categories are not changed.",
                )
            )

            if st.button(
                tr("settings_translate_defaults_btn", "Translate defaults now"),
                type="primary",
                key="settings_translate_defaults_btn",
                use_container_width=True,
            ):
                try:
                    target_lang = (st.session_state.get("language") or "no").strip().lower()
                    cat_n, acc_n = translate_defaults_for_user(user_id=user_id, target_lang=target_lang)
                    st.success(
                        f"{tr('settings_translation_complete', '✅ Translation complete.')}"
                        f" {tr('settings_categories_updated', 'Categories updated')}: {cat_n}, "
                        f"{tr('settings_default_account_updated', 'default account updated')}: {acc_n}"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"{tr('settings_translation_failed', 'Translation failed')}: {e}")

    # ==========================================
    # 2) INTELLIGENCE & ANALYTICS
    # ==========================================
    with tab2:
        col_ai, col_ana = st.columns(2)

        # --- AI PERSONA ---
        with col_ai:
            st.subheader(f"🧠 {tr('settings_ai_persona_title', 'AI Advisor Persona')}")
            st.caption(tr("settings_ai_persona_caption", "Choose how the AI talks to you."))

            persona = get_setting("ai_persona", "Professional Analyst")
            persona_opts = [
                tr("settings_persona_friendly_coach", "Friendly Coach"),
                tr("settings_persona_professional_analyst", "Professional Analyst"),
                tr("settings_persona_strict_accountant", "Strict Accountant"),
                tr("settings_persona_wall_street", "Wall Street Analyst"),
            ]

            # Map back to stored value (keep it stable even if translated)
            # We'll store the raw (English) internal ids instead:
            persona_ids = ["friendly_coach", "professional_analyst", "strict_accountant", "wall_street"]
            persona_id_by_label = dict(zip(persona_opts, persona_ids))
            label_by_persona_id = dict(zip(persona_ids, persona_opts))

            stored_id = get_setting("ai_persona_id", "professional_analyst")
            current_label = label_by_persona_id.get(stored_id, persona_opts[1])
            p_idx = persona_opts.index(current_label) if current_label in persona_opts else 1

            new_label = st.selectbox(
                tr("settings_ai_personality", "AI Personality"),
                persona_opts,
                index=p_idx,
                key="settings_ai_persona_final",
            )
            new_id = persona_id_by_label.get(new_label, "professional_analyst")

            if new_id != stored_id:
                set_setting("ai_persona_id", new_id)
                # Optional: keep old key in sync for backwards compatibility
                set_setting("ai_persona", new_label)
                st.toast(tr("settings_ai_persona_updated", "AI Persona updated!"))

        # --- ANALYTICS SETTINGS ---
        with col_ana:
            st.subheader(f"📊 {tr('settings_analytics_title', 'Analytics Settings')}")
            st.caption(tr("settings_analytics_caption", "Permanently hide specific categories from charts."))

            all_cats_df = load_data_db("categories", user_id=user_id)
            if all_cats_df is not None and not all_cats_df.empty:
                cat_options = sorted(all_cats_df["name"].unique().tolist())
                saved_exclusions = get_setting("analytics_excluded_categories", [])
                valid_selections = [c for c in saved_exclusions if c in cat_options]

                new_exclusions = st.multiselect(
                    tr("settings_excluded_categories", "Excluded Categories"),
                    options=cat_options,
                    default=valid_selections,
                    key="settings_analytics_exclude_final",
                )
                if new_exclusions != saved_exclusions:
                    set_setting("analytics_excluded_categories", new_exclusions)
                    st.toast(tr("settings_analytics_filter_updated", "Analytics filter updated!"))
            else:
                st.info(tr("settings_no_categories_found", "No categories found."))

        st.markdown("---")

        st.subheader(f"🔔 {tr('settings_alerts_defaults', 'Alerts & Defaults')}")
        c3, c4 = st.columns(2)

        # --- BUDGET ALERT THRESHOLD ---
        with c3:
            current_thresh = int(get_setting("budget_alert_threshold", 80))
            new_thresh = st.slider(
                tr("settings_budget_warning_threshold", "Budget Warning Threshold (%)"),
                50,
                100,
                current_thresh,
                step=5,
                key="settings_budget_threshold_final",
            )
            if new_thresh != current_thresh:
                set_setting("budget_alert_threshold", new_thresh)

        # --- DEFAULT ACCOUNT ---
        with c4:
            acc_df = load_data_db("accounts", user_id=user_id)
            if acc_df is not None and not acc_df.empty:
                account_list = sorted(acc_df["name"].unique().tolist())
                current_def_acc = get_setting("default_account_name", account_list[0])
                idx_acc = account_list.index(current_def_acc) if current_def_acc in account_list else 0

                new_def_acc = st.selectbox(
                    tr("settings_default_account", "Default Account"),
                    options=account_list,
                    index=idx_acc,
                    key="settings_default_account_final",
                )
                if new_def_acc != current_def_acc:
                    set_setting("default_account_name", new_def_acc)
            else:
                st.warning(tr("settings_no_accounts_found", "No accounts found."))

    # ==========================================
    # 3) SYSTEM / DATA
    # ==========================================
    with tab3:
        st.subheader(tr("settings_account_data", "Account & Data"))

        # A) CHANGE PASSWORD
        st.markdown(f"### 🔐 {tr('settings_change_password_title', 'Change password')}")
        with st.expander(tr("settings_change_password_expand", "Change password"), expanded=False):
            with st.form("settings_change_password_form"):
                current_pw = st.text_input(tr("settings_current_password", "Current password"), type="password")
                new_pw = st.text_input(tr("settings_new_password", "New password"), type="password")
                new_pw2 = st.text_input(tr("settings_repeat_new_password", "Repeat new password"), type="password")
                submitted = st.form_submit_button(tr("settings_update_password", "Update password"), type="primary")

                if submitted:
                    if not current_pw or not new_pw or not new_pw2:
                        st.error(tr("settings_fill_all_fields", "Please fill all fields."))
                    elif new_pw != new_pw2:
                        st.error(tr("settings_passwords_no_match", "New passwords do not match."))
                    elif len(new_pw) < 8:
                        st.error(tr("settings_password_min_len", "Password must be at least 8 characters."))
                    else:
                        try:
                            with get_connection() as conn:
                                row = conn.execute(
                                    "SELECT password_hash FROM users WHERE username = :u",
                                    {"u": user_id},
                                ).fetchone()

                            stored_hash = (row[0] if row else "") or ""
                            if not stored_hash:
                                st.error(tr("settings_could_not_read_password", "Could not read password for this user."))
                            elif not verify_password(current_pw, stored_hash):
                                st.error(tr("settings_current_password_incorrect", "Current password is incorrect."))
                            else:
                                execute_query_db(
                                    "UPDATE users SET password_hash = :ph WHERE username = :u",
                                    {"ph": hash_password(new_pw), "u": user_id},
                                )
                                st.success(tr("settings_password_updated", "✅ Password updated."))
                                st.toast(tr("settings_password_changed_toast", "Password changed"))
                        except Exception as e:
                            st.error(f"{tr('settings_password_update_failed', 'Password update failed')}: {e}")

        # B) EXPORT DATA
        st.markdown(f"### 📤 {tr('settings_export_data_title', 'Export your data')}")
        with st.expander(tr("settings_export_csv_expand", "Export CSV (transactions, accounts, categories…)"), expanded=False):
            st.caption(tr("settings_export_caption", "Download your data as CSV files. Useful for backup or moving to another app."))

            # Load ALL tables
            c1, c2, c3 = st.columns(3)

            def make_btn(col, table_name, label):
                df = load_data_db(table_name, user_id=user_id)
                with col:
                    st.download_button(
                        f"⬇️ {label}",
                        data=_csv_bytes(df),
                        file_name=f"ziva_{table_name}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

            make_btn(c1, "transactions", tr("transactions", "Transactions"))
            make_btn(c1, "accounts", tr("accounts", "Accounts"))
            make_btn(c1, "categories", tr("categories", "Categories"))

            make_btn(c2, "payees", tr("settings_payees", "Payees"))
            make_btn(c2, "budgets", tr("settings_budgets", "Budgets"))
            make_btn(c2, "recurring", tr("settings_recurring", "Recurring"))

            make_btn(c3, "loans", tr("settings_loans", "Loans"))
            make_btn(c3, "loan_extra_payments", tr("settings_loan_extras", "Loan Extras"))
            make_btn(c3, "loan_terms_history", tr("settings_loan_terms", "Loan Terms"))

            st.caption(tr("settings_export_tip", "Tip: You can import these into Excel / Google Sheets."))

        st.markdown("---")

        # C) FACTORY RESET
        st.subheader(tr("settings_data_management", "Data Management"))
        st.markdown(
            f"""
            <div style="background:#fff1f2; border:1px solid #fda4af; padding:20px; border-radius:10px; margin-bottom:10px;">
                <h4 style="color:#be123c; margin-top:0;">⚠️ {tr("settings_danger_zone", "Danger Zone")}</h4>
                <p style="font-size:13px; color:#881337;">{tr("settings_reset_irreversible", "Resetting your data is irreversible. An automatic backup will be created before deletion.")}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander(tr("settings_factory_reset_expand", "💣 Factory Reset (delete data, keep account)"), expanded=False):
            confirm_text = st.text_input(tr("settings_type_delete_everything", "Type 'DELETE EVERYTHING' to confirm:"), key="settings_factory_reset_confirm_final")
            if st.button(
                tr("settings_confirm_reset", "Confirm Reset"),
                type="primary",
                disabled=(confirm_text != "DELETE EVERYTHING"),
                key="settings_reset_btn_final",
                use_container_width=True,
            ):
                with st.spinner(tr("settings_creating_backup", "Creating safety backup...")):
                    backup_path = create_automatic_backup("pre_factory_reset")

                if backup_path:
                    try:
                        for t_name in ALL_USER_TABLES:
                            execute_query_db(f"DELETE FROM {t_name} WHERE user_id = :uid", {"uid": user_id})
                        st.success(tr("settings_reset_complete", "System reset complete."))
                        st.rerun()
                    except Exception as e:
                        st.error(f"{tr('settings_reset_failed', 'Reset failed')}: {e}")
                else:
                    st.error(tr("settings_backup_failed_reset_aborted", "Backup failed. Reset aborted for safety."))

        # D) DELETE ACCOUNT
        st.markdown(f"### 🧨 {tr('settings_delete_account_title', 'Delete account')}")
        with st.expander(tr("settings_delete_account_expand", "Delete my account permanently"), expanded=False):
            st.warning(tr("settings_delete_warning", "This will delete your user profile AND all your data. This cannot be undone."))
            st.caption(tr("settings_delete_recommend_export", "We recommend exporting your CSV first."))

            confirm_a = st.text_input(tr("settings_type_delete_to_confirm", "Type DELETE to confirm"), key="settings_delete_account_confirm_a")
            confirm_b = st.text_input(tr("settings_type_email_to_confirm", "Type your email to confirm"), value="", key="settings_delete_account_confirm_b").strip().lower()

            delete_ok = (confirm_a.strip().upper() == "DELETE") and (confirm_b == user_email) and bool(user_email)

            if st.button(
                tr("settings_delete_account_btn", "Delete account permanently"),
                type="primary",
                disabled=not delete_ok,
                use_container_width=True,
            ):
                with st.spinner(tr("settings_creating_backup", "Creating safety backup...")):
                    backup_path = create_automatic_backup("pre_delete_account")

                if not backup_path:
                    st.error(tr("settings_backup_failed_delete_aborted", "Backup failed. Delete aborted for safety."))
                    st.stop()

                try:
                    for t_name in ALL_USER_TABLES:
                        try:
                            execute_query_db(f"DELETE FROM {t_name} WHERE user_id = :uid", {"uid": user_id})
                        except Exception:
                            pass

                    execute_query_db("DELETE FROM users WHERE username = :u", {"u": user_id})

                    for k in list(st.session_state.keys()):
                        st.session_state.pop(k, None)

                    st.success(tr("settings_account_deleted", "✅ Your account has been deleted."))
                    st.rerun()

                except Exception as e:
                    st.error(f"{tr('settings_account_deletion_failed', 'Account deletion failed')}: {e}")


def render_admin_user_manager():
    """Admin tools strictly for user and license data management."""
    users = get_all_users_admin()
    if not users:
        st.info(tr("settings_no_users_found", "No users found."))
        return

    user_df = pd.DataFrame(users, columns=["Username", "Role", "License"])
    st.dataframe(user_df, use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        user_to_reset = st.selectbox(
            tr("settings_select_user_to_reset", "Select User to Reset"),
            [u[0] for u in users],
            key="admin_user_reset_sel",
        )
    with col2:
        new_pass = st.text_input(tr("settings_new_temp_password", "New Temporary Password"), type="password", key="admin_user_reset_pass")

    if st.button(tr("settings_update_user_password", "Update User Password (bcrypt)"), key="admin_update_pass_btn", use_container_width=True):
        if not user_to_reset or not new_pass:
            st.error(tr("settings_pick_user_and_password", "Pick a user and enter a password."))
            return
        if len(new_pass) < 8:
            st.error(tr("settings_password_min_len", "Password must be at least 8 characters."))
            return

        ok = execute_query_db(
            "UPDATE users SET password_hash = :ph WHERE username = :u",
            {"ph": hash_password(new_pass), "u": user_to_reset},
        )
        if ok:
            st.success(f"{tr('settings_password_updated_for', 'Password for')} {user_to_reset} {tr('settings_updated', 'updated!')}")
        else:
            st.error(tr("settings_password_update_failed_generic", "Password update failed."))
