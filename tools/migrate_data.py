# migrate_data.py
import json
import pandas as pd
from datetime import datetime
from core.database import get_db_connection
from core.file_operations import get_user_filepath, load_json_file
import os


def migrate_transactions():
    """Migrate transactions from JSON to database"""
    print("🔄 Migrating transactions from JSON to database...")

    # Load existing JSON data using the compatibility function
    transactions_data = load_json_file(get_user_filepath("transactions.json"), [])

    if transactions_data:
        conn = get_db_connection()

        migrated_count = 0
        for transaction in transactions_data:
            # Convert to database format
            conn.execute(
                """
                INSERT OR IGNORE INTO transactions 
                (user_id, account_id, date, description, amount, type, category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    1,  # Default user_id
                    1,  # Default account_id
                    transaction.get("Date", ""),
                    transaction.get("Description", ""),
                    transaction.get("Amount", 0),
                    transaction.get("Type", "Expense"),
                    transaction.get("Category", "Other"),
                ),
            )
            migrated_count += 1

        conn.commit()
        conn.close()
        print(f"✅ Migrated {migrated_count} transactions to database")
    else:
        print("ℹ️ No transactions data found to migrate")


def migrate_accounts():
    """Migrate accounts from JSON to database"""
    print("🔄 Migrating accounts from JSON to database...")

    accounts_data = load_json_file(get_user_filepath("accounts.json"), [])

    if accounts_data:
        conn = get_db_connection()

        migrated_count = 0
        for account in accounts_data:
            conn.execute(
                """
                INSERT OR IGNORE INTO accounts 
                (user_id, name, type, balance, currency)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    1,  # Default user_id
                    account.get("name", ""),
                    account.get("type", "Checking"),
                    account.get("balance", 0),
                    account.get("currency", "USD"),
                ),
            )
            migrated_count += 1

        conn.commit()
        conn.close()
        print(f"✅ Migrated {migrated_count} accounts to database")
    else:
        print("ℹ️ No accounts data found to migrate")


def migrate_budgets():
    """Migrate budgets from JSON to database"""
    print("🔄 Migrating budgets from JSON to database...")

    budgets_data = load_json_file(get_user_filepath("budgets.json"), [])

    if budgets_data:
        conn = get_db_connection()

        migrated_count = 0
        if isinstance(budgets_data, dict):
            # Old format: {"Food": 400, "Transport": 200}
            for category, amount in budgets_data.items():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO budgets 
                    (user_id, category, amount, period)
                    VALUES (?, ?, ?, ?)
                """,
                    (1, category, amount, "Monthly"),
                )
                migrated_count += 1
        else:
            # New format: list of dictionaries
            for budget in budgets_data:
                if isinstance(budget, dict):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO budgets 
                        (user_id, category, amount, period)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            1,  # Default user_id
                            budget.get("category", ""),
                            budget.get("amount", 0),
                            "Monthly",
                        ),
                    )
                    migrated_count += 1

        conn.commit()
        conn.close()
        print(f"✅ Migrated {migrated_count} budget categories to database")
    else:
        print("ℹ️ No budgets data found to migrate")


def migrate_loans():
    """Migrate loans from JSON to database"""
    print("🔄 Migrating loans from JSON to database...")

    loans_data = load_json_file(get_user_filepath("loans.json"), [])

    if loans_data:
        conn = get_db_connection()

        migrated_count = 0
        for loan in loans_data:
            conn.execute(
                """
                INSERT OR IGNORE INTO loans 
                (user_id, name, original_amount, remaining_balance, interest_rate, monthly_payment, start_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    1,  # Default user_id
                    loan.get("name", ""),
                    loan.get("original_amount", 0),
                    loan.get("remaining_balance", 0),
                    loan.get("interest_rate", 0),
                    loan.get("monthly_payment", 0),
                    loan.get("start_date", "2024-01-01"),
                ),
            )
            migrated_count += 1

        conn.commit()
        conn.close()
        print(f"✅ Migrated {migrated_count} loans to database")
    else:
        print("ℹ️ No loans data found to migrate")


def migrate_all_data():
    """Migrate all existing JSON data to database"""
    print("🚀 Starting data migration from JSON to SQLite database...")

    migrate_transactions()
    migrate_accounts()
    migrate_budgets()
    migrate_loans()

    print("🎉 Data migration completed!")


if __name__ == "__main__":
    migrate_all_data()
