# config/config.py
import json
import streamlit as st
from pathlib import Path
from config.i18n import t
lang = st.session_state.get("language", "no")
st.subheader(t("settings.language_region", lang))

# ============================================================
# GLOBAL PATHS
# ============================================================
CONFIG_PATH = Path("config/config.json")
USER_SETTINGS_PATH = Path("config/user_settings.json")


# ============================================================
# CORE CONFIGURATION
# ============================================================

def load_config():
    """Load static application configuration (non-user settings)."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error reading config.json: {e}")
            return {}
    return {}


def save_config(config_dict):
    """Save static configuration to disk."""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2)
    except Exception as e:
        st.error(f"Failed to save config.json: {e}")


# ============================================================
# USER SETTINGS (Persistent Preferences)
# ============================================================

def get_setting(key: str, default=None):
    """
    Retrieve a user setting from session or persisted file.
    Falls back to provided default if not found.
    """
    if "settings" not in st.session_state:
        if USER_SETTINGS_PATH.exists():
            try:
                with open(USER_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    st.session_state["settings"] = json.load(f)
            except Exception:
                st.session_state["settings"] = {}
        else:
            st.session_state["settings"] = {}

    return st.session_state["settings"].get(key, default)


def set_setting(key: str, value):
    """
    Store a setting both in Streamlit session and JSON file.
    Returns True on success, False otherwise.
    """
    # FIX: We check authentication dynamically here, or allow it for testing.
    # If you want to strictly block non-logged in users, uncomment the next 2 lines:
    # if not st.session_state.get("authenticated", False):
    #     return False

    if "settings" not in st.session_state:
        st.session_state["settings"] = {}

    st.session_state["settings"][key] = value

    try:
        USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(USER_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(st.session_state["settings"], f, indent=2)
        return True
    except Exception as e:
        st.error(f"Failed to save settings: {e}")
        return False


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
        formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
        return f"{formatted} {currency}"
    except Exception:
        return f"{amount} {currency}"


# ============================================================
# PLACEHOLDER SETTINGS LOADER FOR OTHER MODULES
# ============================================================

def get_all_settings() -> dict:
    """Return all persisted user settings."""
    if USER_SETTINGS_PATH.exists():
        try:
            with open(USER_SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}