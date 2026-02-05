import streamlit as st
from core.db_operations import get_dataframe_db

st.title("Debug: Users table")

df = get_dataframe_db(
    "SELECT username, email, full_name, password_hash FROM users"
)

st.dataframe(df)
