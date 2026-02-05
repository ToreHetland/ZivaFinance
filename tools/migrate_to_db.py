# migrate_to_db.py
import pandas as pd
import json
import sqlite3
from core.database import DB_NAME, initialize_database


def migrate_data():
    """Migrates data from JSON/CSV files to the SQLite database."""
    # Ensure tables exist
    initialize_database()

    conn = sqlite3.connect(DB_NAME)

    print("Starting data migration...")

    # 1. Migrate Transactions
    try:
        df_trans = pd.read_csv("transactions.csv")
        df_trans.to_sql("transactions", conn, if_exists="append", index=False)
        print(f"Migrated {len(df_trans)} transactions.")
    except Exception as e:
        print(f"Could not migrate transactions: {e}")

    # 2. Migrate Accounts
    try:
        with open("accounts.json", "r") as f:
            accounts = json.load(f)
        df_acc = pd.DataFrame(accounts)
        df_acc = df_acc.rename(columns={"Name": "name", "Type": "account_type"})
        # We only need name and type for this simple migration
        df_acc[["name", "account_type"]].to_sql("accounts", conn, if_exists="append", index=False)
        print(f"Migrated {len(df_acc)} accounts.")
    except Exception as e:
        print(f"Could not migrate accounts: {e}")

    # 3. Migrate Users
    try:
        with open("users.json", "r") as f:
            users = json.load(f)
        df_users = pd.DataFrame(users)
        df_users = df_users.rename(
            columns={"Initials": "initials", "FullName": "full_name", "DataProfile": "data_profile"}
        )
        df_users.to_sql("users", conn, if_exists="append", index=False)
        print(f"Migrated {len(df_users)} users.")
    except Exception as e:
        print(f"Could not migrate users: {e}")

    # 4. Migrate Payees
    try:
        with open("payees.json", "r") as f:
            payees = json.load(f)
        df_payees = pd.DataFrame(payees, columns=["name"])
        df_payees.to_sql("payees", conn, if_exists="append", index=False)
        print(f"Migrated {len(df_payees)} payees.")
    except Exception as e:
        print(f"Could not migrate payees: {e}")

    conn.commit()
    conn.close()
    print("\nMigration complete! You can now run the main application.")
    print("You only need to run this script once.")


if __name__ == "__main__":
    migrate_data()
