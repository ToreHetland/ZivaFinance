import streamlit as st
from supabase import create_client, Client
from config.i18n import t

# ============================================================
# SUPABASE CLIENT INITIALIZATION
# ============================================================

@st.cache_resource
def get_supabase() -> Client:
    """
    Initializes the Supabase client using Streamlit secrets.
    Ensure SUPABASE_URL and SUPABASE_KEY are in your Cloud Secrets.
    """
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# ============================================================
# CORE CONFIGURATION (Static App Data)
# ============================================================

def load_config():
    """
    In cloud environments, static config is best kept in st.secrets 
    or constants. This now returns a default empty dict or secrets.
    """
    return st.secrets.get("app_config", {})

def save_config(config_dict):
    """
    Saving static app config to disk is disabled in the cloud.
    Use the Streamlit Dashboard to update secrets instead.
    """
    st.warning("Manual config saving is disabled in cloud mode. Update secrets instead.")

# ============================================================
# USER SETTINGS (Persistent Preferences via Supabase)
# ============================================================

def get_setting(key: str, default=None):
    """
    Retrieve a user setting from Supabase.
    Logic: Fetches from the 'user_settings' table for the current user.
    """
    # 1. Check if we already have it in this session to save API calls
    if "settings" not in st.session_state:
        st.session_state["settings"] = {}
        
        # 2. If user is logged in, fetch their persistent data from Supabase
        user = st.session_state.get("user")
        if user:
            try:
                supabase = get_supabase()
                # Assumes you have a table 'user_settings' with 'user_id' and 'settings' columns
                response = supabase.table("user_settings")\
                    .select("settings")\
                    .eq("user_id", user["id"])\
                    .execute()
                
                if response.data:
                    st.session_state["settings"] = response.data[0].get("settings", {})
            except Exception as e:
                st.error(f"Error fetching settings from Supabase: {e}")

    return st.session_state["settings"].get(key, default)

def set_setting(key: str, value):
    """
    Upserts a setting into the Supabase 'user_settings' table.
    """
    # Update local session state first
    if "settings" not in st.session_state:
        st.session_state["settings"] = {}
    
    st.session_state["settings"][key] = value

    # Persist to Supabase if authenticated
    user = st.session_state.get("user")
    if user:
        try:
            supabase = get_supabase()
            supabase.table("user_settings").upsert({
                "user_id": user["id"],
                "settings": st.session_state["settings"]
            }).execute()
            return True
        except Exception as e:
            st.error(f"Failed to sync settings to Supabase: {e}")
            return False
    return True

# ============================================================
# CURRENCY FORMATTING
# ============================================================

def format_currency(amount: float) -> str:
    """
    Return formatted currency string based on saved preference.
    Example: 1234.5 -> '1 234,50 NOK'
    """
    if amount is None:
        return "0"

    currency = get_setting("currency", "NOK")
    try:
        # Format with spaces for thousands and comma for decimals
        formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
        return f"{formatted} {currency}"
    except Exception:
        return f"{amount} {currency}"

# ============================================================
# SETTINGS LOADER FOR OTHER MODULES
# ============================================================

def get_all_settings() -> dict:
    """Return all persisted user settings from the current session."""
    return st.session_state.get("settings", {})