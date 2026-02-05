# config/config.py
import streamlit as st
from supabase import create_client, Client
from config.i18n import t

# ============================================================
# SUPABASE CLIENT INITIALIZATION
# ============================================================

@st.cache_resource
def get_supabase() -> Client:
    """Initializes the Supabase client using Streamlit secrets."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# ============================================================
# USER SETTINGS (Persistent Preferences via Supabase)
# ============================================================

def get_setting(key: str, default=None):
    """Retrieve a user setting from the Supabase 'user_settings' table."""
    if "settings" not in st.session_state:
        st.session_state["settings"] = {}
        
        # If user is authenticated, fetch their settings from DB
        if st.session_state.get("authenticated"):
            try:
                supabase = get_supabase()
                user_id = st.session_state.get("username")
                response = supabase.table("user_settings").select("settings").eq("user_id", user_id).execute()
                if response.data:
                    st.session_state["settings"] = response.data[0].get("settings", {})
            except Exception as e:
                st.error(f"Error fetching settings: {e}")

    return st.session_state["settings"].get(key, default)

def set_setting(key: str, value):
    """Updates a setting in Supabase."""
    if "settings" not in st.session_state:
        st.session_state["settings"] = {}
    
    st.session_state["settings"][key] = value

    if st.session_state.get("authenticated"):
        try:
            supabase = get_supabase()
            user_id = st.session_state.get("username")
            supabase.table("user_settings").upsert({
                "user_id": user_id,
                "settings": st.session_state["settings"]
            }).execute()
            return True
        except Exception:
            return False
    return True

def load_config():
    """Static config loader (returning empty dict for cloud compatibility)."""
    return {}

def format_currency(amount: float) -> str:
    """Formatted currency string based on saved preference."""
    if amount is None: return "0"
    currency = get_setting("currency", "NOK")
    try:
        formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
        return f"{formatted} {currency}"
    except Exception:
        return f"{amount} {currency}"