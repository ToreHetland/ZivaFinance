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
from passlib.context import CryptContext

# ============================================================
# PASSWORD HASHING (B2C SAFE)
# ============================================================
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    if not password: raise ValueError("Password cannot be empty")
    return _pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash: return False
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception: return False

# ============================================================
# 1) DATABASE CONNECTION SETUP
# ============================================================
def _get_db_url() -> tuple[str, bool]:
    db_url = st.secrets.get("DATABASE_URL")
    if not db_url:
        project_root = Path(__file__).resolve().parents[1]
        db_dir = project_root / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = (db_dir / "finance.db").resolve()
        return f"sqlite:///{db_path.as_posix()}", False
    return str(db_url).replace("postgres://", "postgresql://"), True

DB_URL, IS_POSTGRES = _get_db_url()

@st.cache_resource
def get_engine() -> Engine | None:
    try:
        return create_engine(DB_URL, pool_pre_ping=True, connect_args={'connect_timeout': 10} if IS_POSTGRES else {})
    except Exception as e:
        st.error(f"❌ DB Connection Error: {e}")
        return None

# ============================================================
# 2) TRANSACTION-SAFE CONNECTION WRAPPER
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
            if exc_type: self.tx.rollback()
            else: self.tx.commit()
        finally:
            if self.conn: self.conn.close()
    def execute(self, query: str, params: dict | list | None = None):
        stmt = text(query) if isinstance(query, str) else query
        return self.conn.execute(stmt, params or {})

def get_connection() -> DBConnectionWrapper:
    engine = get_engine()
    if engine is None: raise RuntimeError("Database engine is not available.")
    return DBConnectionWrapper(engine)

def execute_query_db(query: str, params: dict | None = None, fetch_result: bool = False) -> bool | list:
    try:
        with get_connection() as conn:
            result = conn.execute(query, params)
            if fetch_result: return result.mappings().all()
        return True
    except Exception as e:
        print(f"Execute Query Failed: {e}")
        return False if not fetch_result else []

# ============================================================
# 3) CRUD HELPERS (REQUIRED FOR ONBOARDING & DASHBOARD)
# ============================================================
def add_record_db(table: str, data: dict | list[dict]):
    if not data: return True
    records = data if isinstance(data, list) else [data]
    cleaned_records = []
    for r in records:
        r_copy = r.copy()
        if "id" in r_copy and (not r_copy["id"] or str(r_copy["id"]).strip() == ""):
            r_copy.pop("id", None)
        cleaned_records.append(r_copy)
    first_record = cleaned_records[0]
    columns = ", ".join(first_record.keys())
    placeholders = ", ".join([f":{k}" for k in first_record.keys()])
    query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    with get_connection() as conn:
        return conn.execute(query, cleaned_records)

def get_dataframe_db(query: str, params: dict | None = None) -> pd.DataFrame:
    engine = get_engine()
    if engine is None: return pd.DataFrame()
    with engine.connect() as conn:
        return pd.read_sql(text(str(query)), conn, params=params)

def load_data_db(table_name: str, **kwargs) -> pd.DataFrame:
    allowed = ["users", "licenses", "transactions", "accounts", "categories", "payees", "recurring", "budgets", "loans", "email_settings", "loan_extra_payments", "loan_terms_history"]
    if table_name not in allowed: return pd.DataFrame()
    query = f"SELECT * FROM {table_name}"
    params = {}
    if "user_id" in kwargs and kwargs["user_id"] != "bypass":
        query += " WHERE user_id = :user_id"
        params["user_id"] = kwargs["user_id"]
    return get_dataframe_db(query, params)

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
# 4) APP-SPECIFIC HELPERS (REQUIRED BY AUTH)
# ============================================================
def seed_user_categories(user_id: str) -> None:
    defaults = [("Groceries", "expense", None), ("Salary", "income", None)]
    for name, ctype, parent in defaults:
        ensure_category_exists(name, ctype, user_id=user_id, parent=parent)

def ensure_category_exists(category_name: str, category_type: str, user_id: str, parent: str | None = None) -> None:
    if not category_name: return
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM categories WHERE name = :n AND user_id = :u", {"n": category_name, "u": user_id}).fetchone()
        if not row:
            conn.execute("INSERT INTO categories (name, type, parent_category, user_id) VALUES (:n, :t, :p, :u)", 
                         {"n": category_name, "t": category_type, "p": parent, "u": user_id})

def send_license_request_email(name, email, note): return False
def send_password_reset_email(to_email, reset_link): return False

# ============================================================
# 5) PASSWORD RESET
# ============================================================
def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_password_reset(email: str) -> str | None:
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(raw_token)
    try:
        execute_query_db("INSERT INTO password_resets (email, token_hash, used) VALUES (:e, :th, false)", 
                         {"e": email, "th": token_hash})
        return raw_token
    except Exception: return None

def reset_password_with_token(raw_token: str, new_password: str) -> bool:
    token_hash = _hash_reset_token(raw_token)
    row = execute_query_db("SELECT email FROM password_resets WHERE token_hash = :th AND used = false", {"th": token_hash}, fetch_result=True)
    if row:
        email = row[0]['email']
        execute_query_db("UPDATE users SET password_hash = :ph WHERE email = :e", {"ph": hash_password(new_password), "e": email})
        execute_query_db("UPDATE password_resets SET used = true WHERE token_hash = :th", {"th": token_hash})
        return True
    return False

# init_db()  <-- Keep commented out for Streamlit Cloud