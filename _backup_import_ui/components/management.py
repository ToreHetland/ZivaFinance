# components/management.py
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from config.i18n import t, available_languages, set_language, get_current_language
from config.config import format_currency, load_config, get_setting, set_setting
from core.db_operations import (
    load_data_db,
    save_data_db,
    add_record_db,
    execute_query_db,
    normalize_date_to_iso,
    normalize_type,
    ensure_category_exists,
    ensure_payee_exists,
    get_unique_values_db,  
)
from core.calculations import calculate_monthly_payment
from config.i18n import t

lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))


def render_management_dashboard():
    """Render the management dashboard with tabs"""
    st.header(t("management_dashboard"))

    tabs = st.tabs(
        [
            t("manage_accounts"),
            t("manage_categories"),
            t("manage_payees"),
            t("manage_recurring"),
            t("admin_settings"),
            "🌐 " + t("system_settings"),
        ]
    )

    with tabs[0]:
        render_accounts_management()
    with tabs[1]:
        render_categories_management()
    with tabs[2]:
        render_payees_management()
    with tabs[3]:
        render_recurring_management()
    with tabs[4]:
        render_admin_settings()
    with tabs[5]:
        render_system_settings()


# ============================================================
# ACCOUNTS
# ============================================================


def render_accounts_management():
    """Manage accounts using data from the database."""
    st.subheader(t("manage_accounts"))

    account_df = load_data_db("accounts")

    st.write("**Current Accounts:**")
    edited_account_df = st.data_editor(
        account_df,
        num_rows="dynamic",
        column_config={
            "id": None,
            "name": st.column_config.TextColumn("Account Name", required=True),
            "account_type": st.column_config.SelectboxColumn(
                "Account Type", options=["Checking", "Savings", "Credit Card"], required=True
            ),
            "balance": st.column_config.NumberColumn(
                "Initial Balance", format="%.2f", disabled=True
            ),
            "currency": st.column_config.TextColumn("Currency"),
        },
        key="accounts_editor",
    )

    if st.button(t("save_account_changes_button"), key="save_accounts_btn"):
        if save_data_db(edited_account_df, "accounts", if_exists="replace"):
            st.success(t("account_list_updated_success"))
            st.rerun()


# ============================================================
# CATEGORIES
# ============================================================


def render_categories_management():
    """Manage categories using data from the database."""
    st.subheader(t("manage_categories"))

    categories_df = load_data_db("categories")

    st.write("**Current Categories:**")
    edited_categories_df = st.data_editor(
        categories_df,
        num_rows="dynamic",
        column_config={
            "name": st.column_config.TextColumn("Category Name", required=True),
            "type": st.column_config.SelectboxColumn(
                "Type", options=["Income", "Expense"], required=True
            ),
        },
        key="categories_editor",
    )

    if st.button(t("save_changes_button"), key="save_categories_btn"):
        if save_data_db(edited_categories_df, "categories", if_exists="replace"):
            st.success("Categories updated successfully!")
            st.rerun()


# ============================================================
# PAYEES
# ============================================================


def render_payees_management():
    """Manage payees using data from the database."""
    st.subheader(t("manage_payees"))

    payees_df = load_data_db("payees")

    st.write("**Current Payees:**")
    edited_payees_df = st.data_editor(
        payees_df,
        num_rows="dynamic",
        column_config={"name": st.column_config.TextColumn("Payee Name", required=True)},
        key="payees_editor",
    )

    if st.button(t("save_payee_changes_button"), key="save_payees_btn"):
        if save_data_db(edited_payees_df, "payees", if_exists="replace"):
            st.success(t("payee_list_updated_success"))
            st.rerun()


# ============================================================
# RECURRING TRANSACTIONS
# ============================================================


def render_recurring_management():
    """Manage recurring transactions from the database."""
    st.subheader(t("manage_recurring"))

    recurring_df = load_data_db("recurring")

    st.write("**Current Recurring Rules:**")
    edited_recurring_df = st.data_editor(
        recurring_df, num_rows="dynamic", column_config={"id": None}, key="recurring_editor"
    )

    if st.button(t("save_recurring_changes_button"), key="save_recurring_btn"):
        if save_data_db(edited_recurring_df, "recurring", if_exists="replace"):
            st.success(t("recurring_updated_success"))
            st.rerun()


# ============================================================
# ADMIN USERS
# ============================================================
def render_admin_settings():
    """Manage admin users from the database."""
    st.subheader(t("admin_settings"))

    st.write(f"**{t('manage_users')}**")
    users_df = load_data_db("users")

    edited_users_df = st.data_editor(
        users_df,
        num_rows="dynamic",
        column_config={
            "initials": st.column_config.TextColumn("Initials", max_chars=3, required=True),
            "full_name": st.column_config.TextColumn("Full Name", required=True),
            "data_profile": st.column_config.TextColumn("Data Profile"),
        },
        key="users_editor",
    )

    if st.button(t("save_user_changes_button"), key="save_users_btn"):
        if save_data_db(edited_users_df, "users", if_exists="replace"):
            st.success(t("users_updated_success"))
            st.rerun()


def render_system_settings():
    """Placeholder: System settings currently disabled."""
    st.subheader("🌐 System Settings")
    st.info("Language, theme, and currency options are temporarily hidden for consistency.")
