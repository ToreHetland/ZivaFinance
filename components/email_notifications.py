# components/email_notifications.py
from __future__ import annotations

from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

import pandas as pd
import streamlit as st

from config.i18n import t
from core.db_operations import load_data_db, execute_query_db

# Optional helpers (Cloud-safe)
try:
    from core.db_operations import add_record_db
except ImportError:
    add_record_db = None

try:
    from core.db_operations import save_data_db
except ImportError:
    # Fallback: save via insert/update using execute_query_db
    def save_data_db(table: str, data, identifier_col: str = "id"):
        return False


# ------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------
def _get_user_id() -> str:
    return st.session_state.get("username", "default")


def _safe_bool(x, default=False) -> bool:
    if x is None:
        return default
    try:
        return bool(x)
    except Exception:
        return default


def _ensure_notification_history_table_exists() -> None:
    """
    Optional: create a lightweight table for logs if you use SQLite fallback.
    On Supabase/Postgres you should create tables via migrations, not here.
    This function is intentionally non-blocking.
    """
    # If you want, you can implement a proper migration tool later.
    return


def _load_email_settings(user_id: str) -> pd.Series | None:
    """
    Tries to load email settings. Supports both:
    - Global single-row settings (no user_id column)
    - Per-user settings (user_id column)
    """
    df = load_data_db("email_settings", user_id="bypass")
    if df is None or df.empty:
        df = load_data_db("email_settings", user_id=user_id)

    if df is None or df.empty:
        return None

    # Prefer exact user match if possible
    if "user_id" in df.columns:
        m = df[df["user_id"].astype(str) == str(user_id)]
        if not m.empty:
            return m.iloc[0]
        # otherwise take first
    return df.iloc[0]


def _upsert_email_settings(user_id: str, payload: dict) -> bool:
    """
    Writes settings using save_data_db if present; otherwise uses SQL fallback.
    This assumes your db_operations.save_data_db supports dict-based upsert.
    """
    # Force user_id if table supports it
    payload = dict(payload)
    payload["user_id"] = user_id

    # If save_data_db exists and is functional, use it
    try:
        ok = save_data_db("email_settings", payload)  # type: ignore
        return bool(ok)
    except Exception:
        pass

    # Fallback: try to update existing row by user_id, else insert
    try:
        existing = load_data_db("email_settings", user_id=user_id)
        if existing is not None and not existing.empty and "user_id" in existing.columns:
            # update by user_id
            set_clause = ", ".join([f"{k} = :{k}" for k in payload.keys() if k != "user_id"])
            q = f"UPDATE email_settings SET {set_clause} WHERE user_id = :user_id"
            return bool(execute_query_db(q, payload))
        else:
            # insert
            cols = ", ".join(payload.keys())
            vals = ", ".join([f":{k}" for k in payload.keys()])
            q = f"INSERT INTO email_settings ({cols}) VALUES ({vals})"
            return bool(execute_query_db(q, payload))
    except Exception:
        return False


def send_email(settings: dict, to_email: str, subject: str, body: str) -> bool:
    """
    Sends an email using SMTP settings from 'settings'.
    Returns True/False and shows Streamlit error on failure.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = settings.get("email_address", "")
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        server = smtplib.SMTP(settings.get("smtp_server", ""), int(settings.get("smtp_port", 587)))
        server.starttls()
        server.login(settings.get("email_address", ""), settings.get("email_password", ""))
        server.sendmail(settings.get("email_address", ""), [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False


def _log_notification(user_id: str, notification_type: str, subject: str, body: str, sent_to: str, status: str) -> None:
    if add_record_db is None:
        return
    try:
        add_record_db("notification_history", {
            "user_id": user_id,
            "type": notification_type,
            "subject": subject,
            "message": body,
            "sent_to": sent_to,
            "status": status,
            "sent_at": datetime.utcnow(),
        })
    except Exception:
        pass


def send_notification(user_id: str, notification_type: str, subject: str, body: str) -> bool:
    """Sends and logs an email notification."""
    settings_row = _load_email_settings(user_id)
    if settings_row is None:
        st.warning("No email settings found. Please configure SMTP settings first.")
        return False

    # Convert to dict safely
    settings = settings_row.to_dict() if hasattr(settings_row, "to_dict") else dict(settings_row)

    if not _safe_bool(settings.get("notifications_enabled"), False):
        st.warning("Notifications are disabled in settings.")
        return False

    recipient = (settings.get("email_address") or "").strip()
    if not recipient:
        st.warning("Recipient email is missing in settings.")
        return False

    ok = send_email(settings, recipient, subject, body)
    _log_notification(user_id, notification_type, subject, body, recipient, "sent" if ok else "failed")
    return ok


# ------------------------------------------------------------
# Page UI
# ------------------------------------------------------------
def email_notifications():
    st.header(f"📧 {t('notifications') if callable(t) else 'Email Notifications'}")

    user_id = _get_user_id()
    _ensure_notification_history_table_exists()

    settings_row = _load_email_settings(user_id)
    settings = settings_row.to_dict() if settings_row is not None and hasattr(settings_row, "to_dict") else {}

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(t("settings") if callable(t) else "Email Configuration")

        with st.form("email_config"):
            email_address = st.text_input(
                "Email Address",
                value=str(settings.get("email_address", "") or ""),
                placeholder="you@example.com",
            )
            smtp_server = st.text_input(
                "SMTP Server",
                value=str(settings.get("smtp_server", "") or "smtp.gmail.com"),
            )
            smtp_port = st.number_input(
                "SMTP Port",
                min_value=1,
                max_value=65535,
                value=int(settings.get("smtp_port", 587) or 587),
                step=1,
            )
            email_password = st.text_input(
                "Email Password",
                type="password",
                value=str(settings.get("email_password", "") or ""),
            )

            st.markdown("#### Notification Preferences")
            notifications_enabled = st.checkbox(
                "Enable Notifications",
                value=_safe_bool(settings.get("notifications_enabled"), False),
            )
            budget_alerts = st.checkbox(
                "Budget Alerts",
                value=_safe_bool(settings.get("budget_alerts"), True),
            )
            low_balance_alerts = st.checkbox(
                "Low Balance Alerts",
                value=_safe_bool(settings.get("low_balance_alerts"), True),
            )
            weekly_summaries = st.checkbox(
                "Weekly Summaries",
                value=_safe_bool(settings.get("weekly_summaries"), True),
            )

            submitted = st.form_submit_button("Save Email Settings")

        if submitted:
            payload = {
                "email_address": email_address.strip(),
                "smtp_server": smtp_server.strip(),
                "smtp_port": int(smtp_port),
                "email_password": email_password,  # store encrypted later if desired
                "notifications_enabled": bool(notifications_enabled),
                "budget_alerts": bool(budget_alerts),
                "low_balance_alerts": bool(low_balance_alerts),
                "weekly_summaries": bool(weekly_summaries),
            }

            if _upsert_email_settings(user_id, payload):
                st.success("Email settings saved!")
                st.rerun()
            else:
                st.error("Failed to save email settings (DB function unavailable or DB error).")

    with col2:
        st.subheader("Test & Actions")

        if st.button("Send Test Email", use_container_width=True):
            send_test_email()

        if st.button("Check Budget Alerts", use_container_width=True):
            check_budget_alerts()

        if st.button("Send Weekly Summary", use_container_width=True):
            send_weekly_summary()

    st.subheader("Notification History (Last 10)")
    try:
        history_df = load_data_db("notification_history", user_id=user_id)
        if history_df is not None and not history_df.empty and "sent_at" in history_df.columns:
            history_df["sent_at"] = pd.to_datetime(history_df["sent_at"], errors="coerce")
            st.dataframe(history_df.sort_values(by="sent_at", ascending=False).head(10), use_container_width=True)
        else:
            st.info("No notifications sent yet.")
    except Exception:
        st.info("No notification history available.")


# ------------------------------------------------------------
# Actions
# ------------------------------------------------------------
def send_test_email():
    user_id = _get_user_id()
    subject = "Test Email from Ziva"
    body = "This is a test email. Your configuration is working correctly!"
    if send_notification(user_id, "test", subject, body):
        st.success("Test email sent!")


def check_budget_alerts():
    """Checks and sends budget alerts based on transaction data."""
    user_id = _get_user_id()

    settings_row = _load_email_settings(user_id)
    if settings_row is None:
        st.info("No email settings configured.")
        return
    settings = settings_row.to_dict()

    if not _safe_bool(settings.get("budget_alerts"), True):
        st.info("Budget alerts are disabled.")
        return

    budgets_df = load_data_db("budgets", user_id=user_id)
    transactions_df = load_data_db("transactions", user_id=user_id)

    if budgets_df is None or budgets_df.empty or transactions_df is None or transactions_df.empty:
        st.info("No budgets or transactions to check.")
        return

    # Normalize types
    if "type" in transactions_df.columns:
        tx_type = transactions_df["type"].astype(str).str.lower()
        expenses_df = transactions_df[tx_type.isin(["expense", "utgift"])]
    else:
        expenses_df = transactions_df

    if expenses_df.empty or "category" not in expenses_df.columns or "amount" not in expenses_df.columns:
        st.info("No expense data available for budget checks.")
        return

    spending_by_cat = expenses_df.groupby("category")["amount"].sum().reset_index()

    alerts_sent = 0
    for _, budget in budgets_df.iterrows():
        cat = budget.get("category")
        budget_amount = budget.get("budget_amount", 0)

        if not cat or not budget_amount:
            continue

        spent = spending_by_cat[spending_by_cat["category"] == cat]
        total_spent = float(spent["amount"].sum()) if not spent.empty else 0.0

        try:
            threshold = total_spent / float(budget_amount)
        except Exception:
            threshold = 0.0

        if threshold >= 0.80:  # 80% threshold
            subject = f"Budget Alert: {cat}"
            body = f"You have spent {total_spent:,.2f} of your {float(budget_amount):,.2f} budget for {cat}."
            if send_notification(user_id, "budget_alert", subject, body):
                alerts_sent += 1

    st.success(f"Checked budgets. Sent {alerts_sent} alert(s).")


def send_weekly_summary():
    """Generates and sends a weekly financial summary."""
    user_id = _get_user_id()

    settings_row = _load_email_settings(user_id)
    if settings_row is None:
        st.info("No email settings configured.")
        return
    settings = settings_row.to_dict()

    if not _safe_bool(settings.get("weekly_summaries"), True):
        st.info("Weekly summaries are disabled.")
        return

    one_week_ago = datetime.now() - timedelta(days=7)

    transactions_df = load_data_db("transactions", user_id=user_id)
    if transactions_df is None or transactions_df.empty or "date" not in transactions_df.columns:
        st.info("No transactions available.")
        return

    tx = transactions_df.copy()
    tx["date"] = pd.to_datetime(tx["date"], errors="coerce")
    tx = tx[tx["date"].dt.tz_localize(None) > one_week_ago]

    if tx.empty:
        st.info("No transactions in the last week.")
        return

    # Normalize type labels
    if "type" in tx.columns:
        ttype = tx["type"].astype(str).str.lower()
    else:
        ttype = pd.Series([""] * len(tx))

    income = float(tx[ttype.isin(["income", "inntekt"])]["amount"].sum()) if "amount" in tx.columns else 0.0
    expense = float(tx[ttype.isin(["expense", "utgift"])]["amount"].sum()) if "amount" in tx.columns else 0.0

    subject = "Your Weekly Financial Summary"
    body = (
        "Here is your summary for the last 7 days:\n"
        f"- Total Income: {income:,.2f}\n"
        f"- Total Expenses: {expense:,.2f}\n"
        f"- Net Flow: {(income - expense):,.2f}\n\n"
        "Keep up the great work!"
    )

    if send_notification(user_id, "weekly_summary", subject, body):
        st.success("Weekly summary sent!")
