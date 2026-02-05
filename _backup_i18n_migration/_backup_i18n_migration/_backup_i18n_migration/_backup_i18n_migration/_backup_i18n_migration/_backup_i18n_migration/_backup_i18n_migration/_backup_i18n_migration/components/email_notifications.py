# components/email_notifications.py
import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from core.db_operations import load_data_db, save_data_db, add_record_db
from core.db_operations import execute_query_db # Eller den relevante funksjonen du bruker
from config.i18n import t

def email_notifications():
    st.header("📧 Email Notifications")

    # Get current email settings
    email_settings_df = load_data_db("email_settings")
    settings = email_settings_df.iloc[0] if not email_settings_df.empty else None

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Email Configuration")
        with st.form("email_config"):
            email_address = st.text_input(
                "Email Address", value=settings["email_address"] if settings is not None else ""
            )
            smtp_server = st.text_input(
                "SMTP Server",
                value=settings["smtp_server"] if settings is not None else "smtp.gmail.com",
            )
            smtp_port = st.number_input(
                "SMTP Port", value=int(settings["smtp_port"]) if settings is not None else 587
            )
            email_password = st.text_input(
                "Email Password",
                type="password",
                value=settings["email_password"] if settings is not None else "",
            )

            st.write("Notification Preferences")
            notifications_enabled = st.checkbox(
                "Enable Notifications",
                value=bool(settings["notifications_enabled"]) if settings is not None else False,
            )
            budget_alerts = st.checkbox(
                "Budget Alerts",
                value=bool(settings["budget_alerts"]) if settings is not None else True,
            )
            low_balance_alerts = st.checkbox(
                "Low Balance Alerts",
                value=bool(settings["low_balance_alerts"]) if settings is not None else True,
            )
            weekly_summaries = st.checkbox(
                "Weekly Summaries",
                value=bool(settings["weekly_summaries"]) if settings is not None else True,
            )

            if st.form_submit_button("Save Email Settings"):
                new_settings = pd.DataFrame(
                    [
                        {
                            "id": 1,
                            "email_address": email_address,
                            "smtp_server": smtp_server,
                            "smtp_port": smtp_port,
                            "email_password": email_password,
                            "notifications_enabled": notifications_enabled,
                            "budget_alerts": budget_alerts,
                            "low_balance_alerts": low_balance_alerts,
                            "weekly_summaries": weekly_summaries,
                        }
                    ]
                )
                if save_data_db("email_settings", new_settings, if_exists="replace"):
                    st.success("Email settings saved!")
                    st.rerun()

    with col2:
        st.subheader("Test & Actions")
        if st.button("Send Test Email"):
            send_test_email()
        if st.button("Check Budget Alerts"):
            check_budget_alerts()
        if st.button("Send Weekly Summary"):
            send_weekly_summary()

    st.subheader("Notification History (Last 10)")
    history_df = load_data_db("notification_history")
    if not history_df.empty:
        st.dataframe(history_df.sort_values(by="sent_at", ascending=False).head(10))
    else:
        st.info("No notifications sent yet.")

def send_email(settings, to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = settings["email_address"]
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(settings["smtp_server"], int(settings["smtp_port"]))
        server.starttls()
        server.login(settings["email_address"], settings["email_password"])
        server.sendmail(settings["email_address"], to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def send_notification(notification_type, subject, body):
    """A wrapper to send and log an email."""
    settings_df = load_data_db("email_settings")
    if settings_df.empty or not settings_df.iloc[0]["notifications_enabled"]:
        st.warning("Notifications are disabled in settings.")
        return False

    settings = settings_df.iloc[0]
    recipient = settings["email_address"]

    if send_email(settings, recipient, subject, body):
        log_data = {
            "type": notification_type,
            "subject": subject,
            "message": body,
            "sent_to": recipient,
            "status": "sent",
        }
        add_record_db("notification_history", log_data)
        return True
    return False

def send_test_email():
    subject = "Test Email from Finance App"
    body = "This is a test email. Your configuration is working correctly!"
    if send_notification("test", subject, body):
        st.success("Test email sent!")

def check_budget_alerts():
    """Checks and sends budget alerts based on transaction data."""
    budgets_df = load_data_db("budgets")
    transactions_df = load_data_db("transactions")
    if budgets_df.empty or transactions_df.empty:
        st.info("No budgets or transactions to check.")
        return

    # This query uses the correct 'transactions' table
    expenses_df = transactions_df[transactions_df["type"] == "Expense"]
    spending_by_cat = expenses_df.groupby("category")["amount"].sum().reset_index()

    alerts_sent = 0
    for _, budget in budgets_df.iterrows():
        spent = spending_by_cat[spending_by_cat["category"] == budget["category"]]
        total_spent = spent["amount"].sum()

        if total_spent / budget["budget_amount"] >= 0.80:  # 80% threshold
            subject = f"Budget Alert: {budget['category']}"
            body = f"You have spent {total_spent:,.2f} of your {budget['budget_amount']:,.2f} budget for {budget['category']}."
            if send_notification("budget_alert", subject, body):
                alerts_sent += 1

    st.success(f"Checked budgets. Sent {alerts_sent} alerts.")

def send_weekly_summary():
    """Generates and sends a weekly financial summary."""
    one_week_ago = datetime.now() - timedelta(days=7)

    transactions_df = load_data_db("transactions")
    recent_trans = transactions_df[
        pd.to_datetime(transactions_df["date"]).dt.tz_localize(None) > one_week_ago
    ]

    if recent_trans.empty:
        st.info("No transactions in the last week.")
        return

    income = recent_trans[recent_trans["type"] == "Income"]["amount"].sum()
    expense = recent_trans[recent_trans["type"] == "Expense"]["amount"].sum()

    subject = "Your Weekly Financial Summary"
    body = f"""
    Here is your summary for the last 7 days:
    - Total Income: {income:,.2f}
    - Total Expenses: {expense:,.2f}
    - Net Flow: {(income - expense):,.2f}
    
    Keep up the great work!
    """
    if send_notification("weekly_summary", subject, body):
        st.success("Weekly summary sent!")
