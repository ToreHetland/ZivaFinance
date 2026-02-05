# core/db_operations.py
from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import secrets
import hashlib
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from config.i18n import t

# ============================================================
# PASSWORD HASHING (B2C SAFE)
# ============================================================

from passlib.context import CryptContext

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    return _pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        return False

# ============================================================
# 1) DATABASE CONNECTION SETUP
# ============================================================

def _get_db_url() -> tuple[str, bool]:
    db_url = None
    try:
        if "connections" in st.secrets and "DATABASE_URL" in st.secrets["connections"]:
            db_url = st.secrets["connections"]["DATABASE_URL"]
        else:
            db_url = st.secrets.get("DATABASE_URL", None)
    except Exception:
        db_url = None

    if not db_url:
        project_root = Path(__file__).resolve().parents[1]
        db_dir = project_root / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = (db_dir / "finance.db").resolve()
        return f"sqlite:///{db_path.as_posix()}", False

    db_url = str(db_url).replace("postgres://", "postgresql://")
    return db_url, True

DB_URL, IS_POSTGRES = _get_db_url()

@st.cache_resource
def get_engine() -> Engine | None:
    try:
        return create_engine(DB_URL, pool_pre_ping=True)
    except Exception as e:
        st.error(f"❌ DB Connection Error: {e}")
        return None

# ============================================================
# 2) SCHEMA DEFINITION
# ============================================================

def init_db() -> None:
    engine = get_engine()
    if not engine:
        return

    pk = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"

    tables: dict[str, str] = {
        "users": """
            username VARCHAR(100) PRIMARY KEY,
            full_name VARCHAR(100),
            email VARCHAR(100),
            password_hash TEXT,
            role VARCHAR(20) DEFAULT 'tester',
            language VARCHAR(10) DEFAULT 'en',
            license_code VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """,
        "licenses": """
            code VARCHAR(50) PRIMARY KEY,
            is_used BOOLEAN DEFAULT FALSE,
            assigned_to VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """,
        "license_requests": f"""
            id {pk},
            email VARCHAR(100),
            name VARCHAR(100),
            reason TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """,
        "email_settings": f"""
            id {pk},
            email_address VARCHAR(100),
            email_password VARCHAR(255),
            smtp_server VARCHAR(100),
            smtp_port INTEGER
        """,
        "transactions": f"""
            id {pk},
            date DATE,
            type VARCHAR(20),
            account VARCHAR(50),
            category VARCHAR(50),
            payee VARCHAR(100),
            amount DECIMAL(15, 2),
            description TEXT,
            user_id VARCHAR(50)
        """,
        "accounts": f"""
            id {pk},
            name VARCHAR(50),
            account_type VARCHAR(20),
            balance DECIMAL(15, 2),
            currency VARCHAR(10) DEFAULT 'NOK',
            is_default BOOLEAN DEFAULT FALSE,
            credit_interest_rate DECIMAL(5,2),
            credit_due_day INTEGER,
            credit_source_account VARCHAR(50),
            credit_period_mode VARCHAR(20),
            credit_start_day INTEGER,
            credit_end_day INTEGER,
            description TEXT,
            created_date TIMESTAMP,
            last_updated TIMESTAMP,
            user_id VARCHAR(50)
        """,
        "categories": f"""
            id {pk},
            name VARCHAR(50),
            type VARCHAR(20),
            parent_category VARCHAR(50),
            user_id VARCHAR(50)
        """,
        "payees": f"""
            id {pk},
            name VARCHAR(100),
            user_id VARCHAR(50)
        """,
        "recurring": f"""
            id {pk},
            type VARCHAR(20),
            account VARCHAR(50),
            category VARCHAR(50),
            payee VARCHAR(100),
            amount DECIMAL(15, 2),
            description TEXT,
            start_date DATE,
            frequency VARCHAR(20),
            interval INTEGER,
            last_generated_date DATE,
            user_id VARCHAR(50)
        """,
        "budgets": f"""
            id {pk},
            month VARCHAR(20),
            category VARCHAR(50),
            budget_amount DECIMAL(15, 2),
            user_id VARCHAR(50)
        """,
        "loans": f"""
            id {pk},
            name VARCHAR(100),
            balance DECIMAL(15, 2),
            interest_rate DECIMAL(5, 2),
            min_payment DECIMAL(15, 2),
            user_id VARCHAR(50)
        """,
        # NEW TABLES FOR LOAN CALCULATOR
        "loan_extra_payments": f"""
            id {pk},
            loan_id INTEGER,
            pay_date DATE,
            amount DECIMAL(15, 2),
            note VARCHAR(255),
            user_id VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """,
        "loan_terms_history": f"""
            id {pk},
            loan_id INTEGER,
            change_date DATE,
            interest_rate DECIMAL(5, 2),
            admin_fee DECIMAL(15, 2),
            note VARCHAR(255),
            user_id VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        """
    }

    with engine.begin() as conn:
        for table_name, columns in tables.items():
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns});"))

# ============================================================
# 3) TRANSACTION-SAFE CONNECTION WRAPPER
# ============================================================

class DBConnectionWrapper:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.conn = None
        self.tx = None

    def __enter__(self) -> "DBConnectionWrapper":
        self.conn = self.engine.connect()
        self.tx = self.conn.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            if exc_type:
                self.tx.rollback()
            else:
                self.tx.commit()
        finally:
            if self.conn:
                self.conn.close()

    def execute(self, query: str, params: dict | list | None = None):
        stmt = text(query) if isinstance(query, str) else query
        return self.conn.execute(stmt, params or {})

def get_connection() -> DBConnectionWrapper:
    engine = get_engine()
    if engine is None:
        raise RuntimeError("Database engine is not available.")
    return DBConnectionWrapper(engine)

def execute_query_db(query: str, params: dict | None = None, fetch_result: bool = False) -> bool | list:
    """
    Executes a query. If fetch_result=True, returns list of dicts.
    """
    try:
        with get_connection() as conn:
            result = conn.execute(query, params)
            if fetch_result:
                return result.mappings().all()
        return True
    except Exception as e:
        print(f"Execute Query Failed: {e}")
        return False if not fetch_result else []

# ============================================================
# 4) CRUD HELPERS
# ============================================================

def _fix_sequence_if_needed(table: str) -> None:
    if not IS_POSTGRES:
        return
    fix_sql = f"""
    SELECT setval(
      pg_get_serial_sequence('{table}','id'),
      COALESCE((SELECT MAX(id) FROM {table}), 0) + 1,
      false
    );
    """
    with get_connection() as conn:
        conn.execute(fix_sql)

def add_record_db(table: str, data: dict | list[dict]):
    """
    Insert record(s). Supports single dict or list of dicts (Bulk Insert).
    """
    if not data:
        return True

    # Normalize input to list for processing
    records = data if isinstance(data, list) else [data]
    
    # 1. Clean 'id' from all records if empty/None
    cleaned_records = []
    for r in records:
        r_copy = r.copy()
        if "id" in r_copy and (r_copy["id"] is None or str(r_copy["id"]).strip() == ""):
            r_copy.pop("id", None)
        cleaned_records.append(r_copy)
    
    if not cleaned_records:
        return True

    # 2. Prepare Query based on first record keys
    first_record = cleaned_records[0]
    columns = ", ".join(first_record.keys())
    placeholders = ", ".join([f":{k}" for k in first_record.keys()])
    query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

    try:
        with get_connection() as conn:
            # SQLAlchemy handles list of dicts automatically for bulk inserts
            return conn.execute(query, cleaned_records)

    except Exception as e:
        msg = str(e).lower()
        if IS_POSTGRES and ("duplicate key value violates unique constraint" in msg) and (f"{table}_pkey" in msg):
            try:
                _fix_sequence_if_needed(table)
                with get_connection() as conn:
                    return conn.execute(query, cleaned_records)
            except Exception:
                pass
        raise

def get_records_db(table: str, filters: dict | None = None):
    query = f"SELECT * FROM {table}"
    params: dict = {}
    if filters:
        conditions = " AND ".join([f"{k} = :{k}" for k in filters.keys()])
        query += f" WHERE {conditions}"
        params = filters

    with get_connection() as conn:
        result = conn.execute(query, params)
        return result.fetchall()

def get_dataframe_db(query: str, params: dict | None = None) -> pd.DataFrame:
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()
    with engine.connect() as conn:
        return pd.read_sql(text(str(query)), conn, params=params)

def update_record_db(table: str, data: dict, identifier_col: str, identifier_val):
    set_clause = ", ".join([f"{k} = :{k}" for k in data.keys()])
    query = f"UPDATE {table} SET {set_clause} WHERE {identifier_col} = :id_val"
    params = {**data, "id_val": identifier_val}
    with get_connection() as conn:
        return conn.execute(query, params)

def delete_record_db(table: str, identifier_col: str, identifier_val):
    query = f"DELETE FROM {table} WHERE {identifier_col} = :id_val"
    with get_connection() as conn:
        return conn.execute(query, {"id_val": identifier_val})

# ============================================================
# 5) APP-SPECIFIC HELPERS
# ============================================================

def load_data_db(table_name: str, **kwargs) -> pd.DataFrame:
    """
    Loads data from a table into a DataFrame with a security whitelist.
    """
    allowed = [
        "users",
        "licenses",
        "license_requests",
        "transactions",
        "accounts",
        "categories",
        "payees",
        "recurring",
        "budgets",
        "budget_rules",
        "loans",
        "email_settings",
        # --- FIXED: Added missing tables ---
        "loan_extra_payments",
        "loan_terms_history"
    ]

    if table_name not in allowed:
        print(f"⚠️ Access Denied: Table '{table_name}' is not in the whitelist.")
        return pd.DataFrame()

    query = f"SELECT * FROM {table_name}"
    params: dict = {}

    if "user_id" in kwargs and kwargs["user_id"] != "bypass":
        query += " WHERE user_id = :user_id"
        params["user_id"] = kwargs["user_id"]

    try:
        return get_dataframe_db(query, params)
    except Exception as e:
        print(f"❌ Load Data Error ({table_name}): {e}")
        return pd.DataFrame()

def admin_reset_password(username: str, new_password_hash: str) -> bool:
    return execute_query_db(
        "UPDATE users SET password_hash = :p WHERE username = :u",
        {"p": new_password_hash, "u": username},
    )

def send_license_request_email(name: str, email: str, note: str) -> bool:
    try:
        print(f"[LICENSE REQUEST] name={name} email={email} note={note}")
        return False
    except Exception:
        return False

def send_approval_email(to_email: str, user_name: str, license_code: str) -> bool:
    try:
        print(f"[APPROVAL EMAIL] to={to_email} user={user_name} code={license_code}")
        return False
    except Exception:
        return False

def normalize_date_to_iso(date_val):
    if date_val is None: return None
    if isinstance(date_val, (datetime.date, datetime.datetime)):
        return date_val.strftime("%Y-%m-%d")
    if isinstance(date_val, str):
        return date_val.split("T")[0]
    return str(date_val)

def normalize_type(type_val) -> str:
    if not type_val: return ""
    return str(type_val).strip().lower()

def ensure_category_exists(category_name: str, category_type: str, user_id: str, parent: str | None = None) -> None:
    if not category_name: return
    query = "SELECT id FROM categories WHERE name = :name AND user_id = :uid"
    params = {"name": category_name, "uid": user_id}
    with get_connection() as conn:
        result = conn.execute(query, params).fetchone()
        if result: return
        insert_query = """
            INSERT INTO categories (name, type, parent_category, user_id)
            VALUES (:name, :type, :parent, :uid)
        """
        conn.execute(insert_query, {"name": category_name, "type": normalize_type(category_type) or "expense", "parent": parent, "uid": user_id})

def ensure_payee_exists(payee_name: str, user_id: str) -> None:
    if not payee_name or str(payee_name).strip() == "": return
    query = "SELECT id FROM payees WHERE name = :name AND user_id = :uid"
    params = {"name": payee_name, "uid": user_id}
    with get_connection() as conn:
        result = conn.execute(query, params).fetchone()
        if result: return
        conn.execute("INSERT INTO payees (name, user_id) VALUES (:name, :uid)", params)

def get_category_type(category_name: str, user_id: str) -> str:
    if not category_name: return "expense"
    query = "SELECT type FROM categories WHERE name = :name AND user_id = :uid"
    params = {"name": category_name, "uid": user_id}
    with get_connection() as conn:
        result = conn.execute(query, params).fetchone()
        if result: return str(result[0]).strip().lower() or "expense"
    return "expense"

def get_all_users_admin():
    query = "SELECT username, role, license_code FROM users ORDER BY username ASC"
    with get_connection() as conn:
        return conn.execute(query).fetchall()

def save_data_db(table: str, data: dict | list[dict], identifier_col: str = "id"):
    """
    Saves data to DB.
    - If list[dict]: Performs Bulk Insert (add_record_db handles it).
    - If dict: Updates if identifier_col exists, else Inserts.
    """
    try:
        # BULK INSERT
        if isinstance(data, list):
            return add_record_db(table, data)

        # SINGLE UPDATE
        if identifier_col in data and data[identifier_col] is not None:
            id_val = data.pop(identifier_col)
            return update_record_db(table, data, identifier_col, id_val)

        # SINGLE INSERT
        if identifier_col in data:
            data.pop(identifier_col)
        return add_record_db(table, data)

    except Exception as e:
        print(f"Error in save_data_db for table {table}: {e}")
        return False

def sanitize_for_db(value):
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned != "" else None
    return value

def seed_user_categories(user_id: str) -> None:
    defaults = [("Groceries", "expense", None), ("Salary", "income", None)] # Shortened for brevity, use full list
    for name, ctype, parent in defaults:
        ensure_category_exists(name, ctype, user_id=user_id, parent=parent)

# ============================================================
# PASSWORD RESET (FORGOT PASSWORD)
# ============================================================
def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_password_reset(email: str, expiry_minutes: int = 30) -> str | None:
    email = (email or "").strip().lower()
    if not email: return None
    try:
        with get_connection() as conn:
            row = conn.execute(text("SELECT email FROM users WHERE lower(email) = :e"), {"e": email}).fetchone()
            if not row: return None
            conn.execute(text("UPDATE password_resets SET used = true WHERE lower(email) = :e AND used = false"), {"e": email})
            raw_token = secrets.token_urlsafe(32)
            token_hash = _hash_reset_token(raw_token)
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=expiry_minutes)
            conn.execute(text("INSERT INTO password_resets (email, token_hash, expires_at, used) VALUES (:email, :th, :exp, false)"), {"email": email, "th": token_hash, "exp": expires_at})
            conn.conn.commit()
            return raw_token
    except Exception: return None

def validate_password_reset_token(raw_token: str) -> str | None:
    if not raw_token: return None
    token_hash = _hash_reset_token(raw_token)
    try:
        with get_connection() as conn:
            row = conn.execute(text("SELECT email, expires_at, used FROM password_resets WHERE token_hash = :th ORDER BY created_at DESC LIMIT 1"), {"th": token_hash}).fetchone()
        if not row or row[2] or (row[1] and row[1] < datetime.datetime.utcnow()): return None
        return (row[0] or "").strip().lower()
    except Exception: return None

def mark_password_reset_used(raw_token: str) -> None:
    if not raw_token: return
    token_hash = _hash_reset_token(raw_token)
    try: execute_query_db("UPDATE password_resets SET used = true WHERE token_hash = :th", {"th": token_hash})
    except Exception: pass

def reset_password_with_token(raw_token: str, new_password: str) -> bool:
    email = validate_password_reset_token(raw_token)
    if not email: return False
    if execute_query_db("UPDATE users SET password_hash = :ph WHERE lower(email) = :e", {"ph": hash_password(new_password), "e": email}):
        mark_password_reset_used(raw_token)
        return True
    return False

def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    return False # Placeholder

init_db()